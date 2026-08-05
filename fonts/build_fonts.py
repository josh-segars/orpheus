#!/usr/bin/env python3
"""
Build self-hosted webfonts for Orpheus.  ORPHEUS font self-hosting.

Design constraints discovered by auditing the repo, not assumed:

  * `opsz` is PRESERVED in full (8-60). The design system sets it explicitly
    in 40+ declarations across 14 files, with values from 15 to 60, so it is
    a first-class token — pinning it would silently flatten every one.
  * `tnum` is KEPT: SignalMeter.css uses `font-variant-numeric: tabular-nums`.
  * `onum` / `frac` / `sups` / `subs` are DROPPED — nothing references them.
    This is where the bytes were: 32 KB per serif face.
  * serif `wght` limited to 300-900; no rule uses a lighter weight than 300.
    Sans keeps its full range (limiting it measured *larger*).
  * Two slices per face on Google's exact unicode-ranges, so latin-ext is
    only fetched when a client name actually needs it.

RENAME rationale — SIL OFL-FAQ 2.6 makes subsetting a Modified Version,
which "would not normally allow the use of RFNs"; 5.3 scopes the restriction
to "the font menu name and other mechanisms that specify a font in a
document". Name IDs 0 (copyright), 7 (trademark), 13 (license) and
14 (license URL) are left VERBATIM, as OFL condition 2 requires.
"""

import re
import shutil
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.subset import Subsetter, Options
from fontTools.varLib import instancer

SRC = Path("/home/claude/fonts")
OUT = Path("/home/claude/fonts_out")

RANGES = {
    "latin": (
        "U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,"
        "U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,"
        "U+2212,U+2215,U+FEFF,U+FFFD"
    ),
    "latin-ext": (
        "U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,"
        "U+0304,U+0308,U+0329,U+1D00-1DBF,U+1E00-1E9F,U+1EF2-1EFF,U+2020,"
        "U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF"
    ),
}

# src file -> (output basename, wght limit or None)
FACES = {
    "SourceSerif4Variable-Roman.ttf.woff2":  ("OrpheusSerif-Roman",  (300, 900)),
    "SourceSerif4Variable-Italic.ttf.woff2": ("OrpheusSerif-Italic", (300, 900)),
    "SourceSans3VF-Upright.ttf.woff2":       ("OrpheusSans-Roman",   None),
    "SourceSans3VF-Italic.ttf.woff2":        ("OrpheusSans-Italic",  None),
}

RENAMES = [
    ("Source Serif 4", "Orpheus Serif"), ("SourceSerif4", "OrpheusSerif"),
    ("Source Serif",   "Orpheus Serif"), ("SourceSerif",  "OrpheusSerif"),
    ("Source Sans 3",  "Orpheus Sans"),  ("SourceSans3",  "OrpheusSans"),
    ("Source Sans",    "Orpheus Sans"),  ("SourceSans",   "OrpheusSans"),
]

PRESERVE_NAME_IDS = {0, 7, 13, 14}

KEEP_FEATURES = ["kern", "liga", "clig", "calt", "ccmp",
                 "mark", "mkmk", "locl", "rlig", "tnum"]


def parse_unicodes(s):
    out = []
    for part in s.split(","):
        part = part.strip().removeprefix("U+")
        if "-" in part:
            lo, hi = part.split("-")
            out.extend(range(int(lo, 16), int(hi, 16) + 1))
        else:
            out.append(int(part, 16))
    return out


def rename_name_table(font):
    for rec in font["name"].names:
        if rec.nameID in PRESERVE_NAME_IDS:
            continue
        try:
            value = rec.toUnicode()
        except Exception:
            continue
        new = value
        for old, repl in RENAMES:
            new = new.replace(old, repl)
        if new != value:
            rec.string = new.encode("utf_16_be" if rec.platformID == 3 else "latin-1")

    leftovers = []
    for rec in font["name"].names:
        if rec.nameID in PRESERVE_NAME_IDS:
            continue
        try:
            v = rec.toUnicode()
        except Exception:
            continue
        if re.search(r"Source\s*(Serif|Sans)", v):
            leftovers.append(f"nameID {rec.nameID}: {v!r}")
    return leftovers


def build(src_name, out_base, wght_limit, slice_name, unicodes):
    font = TTFont(SRC / src_name)

    opts = Options()
    opts.flavor = "woff2"
    opts.name_IDs = [0, 1, 2, 3, 4, 5, 6, 13, 14, 16, 17]
    opts.name_languages = [0x409]
    opts.layout_features = KEEP_FEATURES
    opts.layout_scripts = ["latn", "DFLT"]
    opts.drop_tables = ["DSIG"]
    opts.notdef_outline = True

    sub = Subsetter(options=opts)
    sub.populate(unicodes=parse_unicodes(unicodes))
    sub.subset(font)

    # After subsetting — the reverse order desyncs gvar from glyf.
    if wght_limit:
        instancer.instantiateVariableFont(
            font, {"wght": wght_limit}, inplace=True, updateFontNames=False
        )

    leftovers = rename_name_table(font)

    dest = OUT / f"{out_base}.{slice_name}.woff2"
    font.flavor = "woff2"
    font.save(dest)

    axes = [(a.axisTag, a.minValue, a.maxValue) for a in font["fvar"].axes]
    n = font["maxp"].numGlyphs
    font.close()
    assert not leftovers, f"RFN survived in {dest.name}: {leftovers}"
    return {"file": dest.name, "bytes": dest.stat().st_size, "glyphs": n, "axes": axes}


def main():
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir()

    rows = []
    print(f"{'file':<40} {'glyphs':>7} {'KB':>7}  axes")
    print("-" * 82)
    for src_name, (out_base, wl) in FACES.items():
        for slice_name, unicodes in RANGES.items():
            r = build(src_name, out_base, wl, slice_name, unicodes)
            rows.append((out_base, slice_name, r))
            ax = ", ".join(f"{t} {lo:g}-{hi:g}" for t, lo, hi in r["axes"])
            print(f"{r['file']:<40} {r['glyphs']:>7} {r['bytes']/1024:>6.1f}  {ax}")

    print("-" * 82)
    crit = sum(r["bytes"] for b, s, r in rows if s == "latin" and "Roman" in b)
    ital = sum(r["bytes"] for b, s, r in rows if s == "latin" and "Italic" in b)
    ext = sum(r["bytes"] for b, s, r in rows if s == "latin-ext")
    print(f"CRITICAL PATH  (upright latin)          : {crit/1024:7.1f} KB")
    print(f"  today, via Google (5 per-weight files): {207.1:7.1f} KB")
    print(f"  reduction                             : {100*(1-crit/1024/207.1):6.0f}%")
    print(f"italic latin   (on first italic glyph)  : {ital/1024:7.1f} KB")
    print(f"latin-ext      (on first accented char) : {ext/1024:7.1f} KB")
    print("\nopsz preserved 8-60 on both serif faces — every existing")
    print("font-variation-settings: 'opsz' N declaration keeps working.")


if __name__ == "__main__":
    main()
