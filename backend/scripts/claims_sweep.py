"""ORPHEUS-134/137 acceptance sweep: check generated text against the claims layer.

Regenerates narratives against a job's **already-stored** `ingested_data`, N
times, and sweeps every client-facing string for the breach families Andrew's
v3 review found in the released 2026-08-13 report (job b03ca0f5). Also sweeps
the *stored* delivered text for the same job, which is the control: that text
is known to contain twenty breaches, so a detector that comes back clean on it
is broken, not reassuring.

**This script never writes.** No `scores`, no `narratives`, no `jobs`, no
Storage. It reads, generates in memory, and prints. `regenerate_report.py` is
the one that writes; this one deliberately cannot, so it is safe to point at a
delivered report.

WHAT THIS PROVES, AND WHAT IT DOES NOT
--------------------------------------
Pattern matching finds the breach *families we already know about*. It cannot
prove a generation is clean — a new phrasing of "do X, get more reach" that
nobody has written down yet will pass silently. The 2026-07-27 lesson applies
in full: a clean run is not evidence.

So this script has two outputs and the second one matters more:

  1. A per-family flag report, split into HIGH (verbatim or near-verbatim v3
     constructions, and unambiguous ones) and REVIEW (heuristics that catch
     real breaches but also catch legitimate prose).
  2. **A full dump of every generated string, per run, to a file.** That dump
     is the actual acceptance artifact. Somebody reads it. The flags exist to
     tell that reader where to look first, not to replace them.

Treat a zero-flag run as "nothing known re-appeared", never as "the guardrail
works".

The detector self-tests before every sweep: the five verbatim v3 Part 1
exemplars must all be caught, or the run aborts. That guard is what keeps a
future edit to the patterns from quietly turning this into a rubber stamp.

USAGE
-----
Run from the repo root on a machine with backend deps + env (NOT the Claude
sandbox — API egress is blocked there):

    # detector self-test only, no DB, no API, instant
    python -m backend.scripts.claims_sweep --self-test

    # control: sweep the stored delivered text. No API cost.
    python -m backend.scripts.claims_sweep b03ca0f5 --control

    # the acceptance sweep: 5 fresh generations, ~$0.10 each
    python -m backend.scripts.claims_sweep b03ca0f5 --runs 5

    # both, which is the recommended form
    python -m backend.scripts.claims_sweep b03ca0f5 --control --runs 5

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY; ANTHROPIC_API_KEY only when
--runs is used. Read from the environment, falling back to backend/.env then
.env — same resolution as regenerate_report.py.

Text dumps land in `sweep_<jobprefix>_<stamp>/` at the repo root, untracked.
"""

import argparse
import asyncio
import json
import os
import re
import sys
from datetime import date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from backend.agents import prose_numbers  # noqa: E402
from backend.agents.narrative import (  # noqa: E402
    build_milestone_targets,
    generate_narratives,
)
from backend.ingestion.types import XlsxData, ZipData  # noqa: E402
from backend.models.quality import DataQualityReport  # noqa: E402
from backend.scoring.engine import resolve_ref_date, run_scoring  # noqa: E402

RUBRIC_DIMENSIONS = ("Profile Signal Clarity", "Profile-Behavior Alignment")

# Rough per-call cost of one narrative generation at 8192 max_tokens, carried
# from regenerate_report.py's docstring. Printed so a --runs 20 typo is
# visible as a dollar figure before it spends anything.
COST_PER_RUN_USD = 0.10


# ============================================================
# The breach families
# ============================================================
#
# Sources, in order of authority:
#   - Ruling 2 (Foundational Review FINAL 2026-07-16): "No user-facing
#     'do X -> more reach' claim may ship." Permitted registers are
#     signal-legibility and human-reader effects, human-reader preferred.
#   - Ruling 3: mechanism citable, effect size never.
#   - Andrew's v3 findings (2026-08-13): the five critical breaches, verbatim.
#   - Decision Log 2026-08-16: recommendations excluded everywhere; the product
#     never asserts the absence of anything outside the ingested set.
#
# `tier` is HIGH for patterns that are verbatim/near-verbatim v3 constructions
# or otherwise unambiguous, REVIEW for heuristics that will also fire on
# legitimate prose. Keeping them in one table with an honest tier beats two
# tables where the REVIEW half quietly gets dropped.
#
# `exemplar` is the v3 quote the pattern exists to catch. Every family that
# names one is asserted against it in the self-test, so a pattern edit that
# stops catching the original breach fails loudly.

FAMILIES: list[dict] = [
    {
        "id": "F1-threshold",
        "tier": "HIGH",
        "what": "Threshold assertion — a cutoff the corpus does not document",
        "why": "v3 critical #1, Posting Presence sub-dimension. Spec 2 "
               "prohibits this construction by name.",
        "exemplar": "places you well above the threshold where original "
                    "content meaningfully contributes to a professional "
                    "presence.",
        # 2026-08-18 second sweep: the model relocated the banned cutoff into
        # the permitted human-reader register. Same claim, new clothing.
        "also_catches": [
            "well past the point where your activity pattern is legible to "
            "anyone paying attention",
            "well past where consistent activity builds a recognizable "
            "presence",
            "place you well into the range where your participation is "
            "genuinely substantive",
            "consistent enough that readers who follow you have come to "
            "expect you",
            "The profile is already strong enough to support those goals",
        ],
        "patterns": [
            r"above\s+the\s+threshold",
            r"threshold\s+(?:where|at\s+which|for)",
            r"past\s+the\s+point\s+(?:where|at\s+which)",
            r"\bpast\s+where\b",
            r"in(?:to)?\s+the\s+range\s+where",
            r"enough\s+(?:that|to)\s+(?:readers|support)",
            r"enough\s+\w+(?:\s+\w+){0,3}\s+to\s+register",
            r"crosses?\s+(?:the\s+)?(?:line|bar)\s+(?:where|into)",
        ],
    },
    {
        "id": "F2-behavior-to-reach",
        "tier": "HIGH",
        "what": "Behavior presented as producing reach, scale or exposure",
        "why": "v3 critical #2. Ruling 2 states outbound volume as a driver "
               "of the member's own distribution is NOT supported.",
        "exemplar": "this activity level is generating meaningful scale and "
                    "shows that the volume is translating into genuine "
                    "audience exposure.",
        # 2026-08-18 dump read: reach claims in cheat-sheet priorities that
        # the patterns missed.
        "also_catches": [
            "a cadence where your content is appearing in feeds more "
            "reliably",
            "the lever most likely to pull in the readers whose attention "
            "matters most",
            "the ones most likely to be seen by the audience you're trying "
            "to reach",
            "could amplify what's already working",
            # 2026-08-18 second sweep: hyphenated words broke the verb-gap
            # patterns ("Per-Post", "Post-Level"), and past-tense verbs were
            # never covered.
            "Grow Post-Level Reach",
            "Grow Your Per-Post Reach",
            "Strengthen Per-Post Reach",
            "That consistency has produced observable results in the reach "
            "data",
            "is the kind that builds a recognizable presence across a "
            "network over time",
            "Sustaining that growth rate as you refine your topic mix will "
            "build the audience most relevant",
            "a tighter classification could help surface you in more "
            "relevant searches",
            "become part of the network that surfaces your name",
            "tend to be the ones that travel most broadly",
            "one way to move the per-post average",
        ],
        "patterns": [
            r"generating\s+meaningful\s+scale",
            r"translating\s+into",
            r"appear(?:ing|s)?\s+in\s+(?:the\s+)?feeds?",
            r"pulls?\s+in\s+(?:the\s+)?(?:readers?|audiences?|members|"
            r"attention)",
            r"most\s+likely\s+to\s+be\s+seen",
            r"\bamplif(?:y|ies|ying)",
            r"\b(?:drives?|driving|drove|generates?|generating|generated|"
            r"produces?|producing|produced|creates?|creating|created)"
            r"\s+(?:[\w'-]+\s+){0,4}"
            r"(?:reach|visibility|impressions|exposure|distribution|scale)",
            r"\b(?:increases?|improves?|boosts?|lifts?|expands?|grows?|"
            r"strengthens?)"
            r"\s+(?:your\s+|the\s+)?(?:[\w'-]+\s+){0,2}"
            r"(?:reach|visibility|impressions|exposure|distribution)",
            r"build(?:s|ing)?\s+(?:a\s+|the\s+|your\s+)?"
            r"(?:recognizable\s+|genuine\s+)?(?:presence|audience|following)"
            r"\b",
            r"surfaces?\s+you(?:r\s+name)?\b",
            r"travel(?:s|ed|ing)?\s+(?:most|more)\s+broadly",
            r"move\s+the\s+(?:per-post\s+)?average",
            r"\bmore\s+(?:reach|visibility|impressions|exposure)",
            r"help(?:s|ing)?\s+you\s+(?:get\s+)?(?:seen|noticed|found)",
            r"algorithm\s+(?:rewards?|favou?rs?|picks?\s+up|likes?)",
            r"better\s+chance\s+of\s+(?:spreading|being\s+seen|reaching)",
            r"gets?\s+in\s+front\s+of\s+more",
        ],
    },
    {
        "id": "F3-outcome-promise",
        "tier": "HIGH",
        "what": "Member's own stated goals promised as outcomes the behavior "
                "will deliver",
        "why": "v3 critical #3 — the outcome-promise shape Ruling 2 flags as "
               "highest-stakes for a paying buyer.",
        "exemplar": "the behavioral foundation is already in place to support "
                    "all of those outcomes.",
        "patterns": [
            r"in\s+place\s+to\s+support",
            r"support\s+(?:all\s+of\s+)?(?:those|these)\s+outcomes",
            r"will\s+(?:deliver|produce|achieve|get\s+you)",
            r"(?:sets?|puts?)\s+you\s+up\s+(?:to|for)",
            r"on\s+track\s+(?:to|for)\s+(?:\w+\s+){0,3}"
            r"(?:reach|growth|opportunit|outcome)",
        ],
    },
    {
        "id": "F4-visibility-claim",
        "tier": "HIGH",
        "what": "Breadth or focus claimed to support visibility, or a metric "
                "claimed to improve from a behavior change",
        "why": "v3 critical #4, Signal Quality narrative.",
        "exemplar": "That breadth tends to support wider visibility across "
                    "audience segments, and there is likely room to see that "
                    "rate improve as topic focus sharpens.",
        "patterns": [
            r"(?:tends?\s+to\s+)?support\s+(?:wider|broader|greater)\s+"
            r"(?:visibility|reach|exposure)",
            r"wider\s+visibility",
            r"(?:rate|engagement|reach)\s+(?:to\s+)?improve\s+as",
            r"room\s+to\s+see\s+that\s+\w+\s+improve",
            r"as\s+(?:topic\s+)?focus\s+sharpens",
        ],
    },
    {
        "id": "F5-effect-size",
        "tier": "HIGH",
        "what": "Effect size or ranked leverage attached to a recommendation",
        "why": "v3 critical #5. Ruling 3 permits mechanism and forbids effect "
               "size; 'highest-leverage' is an effect-size claim in words.",
        "exemplar": "is likely the highest-leverage profile-level move "
                    "available to you. This is the single highest-leverage "
                    "move available given your existing volume and reach.",
        # 2026-08-18 second sweep: leverage rankings in fresh wording.
        "also_catches": [
            "the primary lever at this level is continuity of focus",
            "is likely the most important behavioral move you can make",
            "the behavioral work that matters most",
        ],
        "patterns": [
            r"highest[-\s]leverage",
            r"single\s+(?:most|highest|biggest|largest)",
            r"most\s+(?:impactful|effective|powerful)\s+(?:move|change|step)",
            r"most\s+important\s+(?:behavioral\s+)?(?:move|change|step|work)",
            r"primary\s+lever",
            r"work\s+that\s+matters\s+most",
            r"biggest\s+(?:lever|impact|difference|win)",
            r"\d+\s?%\s+(?:more|higher|increase|improvement|lift|better)",
            # 2026-08-18: negative lookahead added — "doubles as a positioning
            # statement" is an idiom, not an effect size, and it inflated run 3
            # of the 08-17 sweep.
            r"\b(?:doubles?|triples?|halves?)\b(?!\s+as\b)",
            r"(?:\d+|two|three|several)\s?(?:x|times)\s+(?:more|the|as)",
        ],
    },
    {
        "id": "F6-attribution-instruction",
        "tier": "HIGH",
        "what": "Member instructed to attribute outcomes to their own "
                "behavior",
        "why": "v3 Part 1, the two weekly-rhythm items: the member is told to "
               "do the attribution the corpus does not support.",
        "exemplar": "notice which angles generated the most response and let "
                    "that inform the following week's framing; note whether "
                    "topic shifts correlate with changes in either metric.",
        # 2026-08-18: expanded with the phrasings the 08-17 and 08-18 dump
        # reads caught by hand while the patterns stayed silent. Each is
        # pinned in `also_catches` so a later edit cannot silently unlearn it.
        "also_catches": [
            "Review your top-performing posts for common patterns and adjust "
            "your content approach accordingly.",
            "which posts drew the most meaningful responses",
            "examine what made it travel further than the others",
            "note which openings, topics, or formats drew the most response "
            "and carry that forward",
            "which post traveled furthest, and what did it have in common "
            "with your other high-performing content",
            "use any significant shift as a prompt to examine what changed "
            "in your content or engagement pattern",
            "adjust your content mix if either is stalling",
            "studying what your highest-performing posts have in common and "
            "applying those patterns more deliberately",
            "assess whether the trend line is moving",
            "identify one post that performed well and consider what made "
            "it land",
            # 2026-08-18 second sweep: the family relocated from the cheat
            # sheet into an improvements[] slot.
            "When personal or Portugal posts perform well, look for ways to "
            "draw a connection to your professional domain",
        ],
        "patterns": [
            r"which\s+\w+\s+generated\s+(?:the\s+)?most",
            r"generated\s+the\s+most\s+(?:response|engagement|reach)",
            r"correlate[sd]?\s+with\s+changes",
            r"notice\s+(?:which|what|whether)\s+(?:\w+\s+){0,3}"
            r"(?:performed|worked|landed|generated|resonated)",
            r"let\s+that\s+inform",
            r"see\s+what\s+(?:works|performs|lands)",
            r"track\s+(?:which|what)\s+(?:\w+\s+){0,3}"
            r"(?:performs?|works?|lands?)",
            r"(?:drew|draws?|drawing)\s+the\s+most",
            r"travel(?:s|ed|led|ing)?\s+(?:further|furthest|farther|farthest)",
            r"adjust\s+(?:your\s+)?content\s+(?:mix|approach|direction|"
            r"strategy)",
            r"whether\s+(?:your\s+|any\s+)?content\s+(?:mix|type|direction)",
            r"(?:high|highest|top|best)[-\s]perform",
            r"appl(?:y|ying)\s+those\s+patterns",
            r"what\s+made\s+(?:it|that|this)\s+(?:land|travel|work|resonate|"
            r"perform)",
            r"what\s+changed\s+in\s+your\s+content",
            r"if\s+either\s+is\s+(?:stalling|drifting|moving)",
            r"whether\s+the\s+trend",
            r"when\s+(?:[\w'-]+\s+){0,4}posts?\s+perform",
        ],
    },
    {
        "id": "F7-absence-assertion",
        "tier": "HIGH",
        "what": "Absence asserted about something outside the ingested set",
        "why": "ORPHEUS-137. The b03ca0f5 report's only outright false claim, "
               "and it spent a top-5 priority slot on it. These phrasings "
               "carry their own evidence of non-observability — you do not "
               "hedge about text sitting in front of you.",
        "exemplar": "Recommendations are not visible in your current profile "
                    "and is one of the few structural elements currently "
                    "absent.",
        "patterns": [
            r"currently\s+absent",
            r"structural\s+elements?\s+(?:currently\s+)?absent",
            r"not\s+visible\s+in\s+your",
            r"(?:is|are)\s+absent\s+from\s+your",
            r"appears?\s+to\s+be\s+missing",
        ],
    },
    {
        "id": "F7b-absence-generic",
        "tier": "REVIEW",
        "what": "Flat absence phrasing whose subject may or may not be in the "
                "ingested set",
        "why": "REVIEW rather than HIGH on purpose: whether this is a breach "
               "depends entirely on WHAT is claimed absent, and a regex "
               "cannot know that. 'You do not have a call to action in your "
               "About section' is legitimate — the About text is ingested and "
               "the agent can see it (Core rule 3). The same sentence about "
               "recommendations is the b03ca0f5 bug. Read the subject of "
               "every hit; do not batch-judge them.",
        "exemplar": None,
        "patterns": [
            r"you\s+(?:do\s+not|don't)\s+have",
            r"you\s+(?:are|'re)\s+missing",
            r"\bno\s+(?:\w+\s+){0,2}(?:present|on\s+your\s+profile)\b",
        ],
    },
    {
        "id": "F8-excluded-subject",
        "tier": "HIGH",
        "what": "Recommendations, endorsements or skill display order, in the "
                "LinkedIn-feature sense",
        "why": "Decision Log 2026-08-16: they appear nowhere in the "
               "deliverable. Not a claim to hedge; a subject not written "
               "about. Patterns here require the feature sense — an action on "
               "recommendations, a possessive, or a presence/absence "
               "statement — so the advice-sense word does not land at HIGH.",
        "exemplar": "Recommendations are not visible in the provided profile "
                    "content; consider reviewing the ordering of your top "
                    "skills, and seek endorsements.",
        # 2026-08-18 dump read: skill-display-order advice in paraphrase.
        # NOTE: skills-LIST-curation advice ("a more curated set") is NOT
        # flagged here — whether set-curation is banned alongside display
        # order is a pending team decision. Only order/prominence language
        # lands at HIGH.
        "also_catches": [
            "prioritizing the skills most directly relevant to your current "
            "work could help",
            "a more curated front-of-list could sharpen the first impression",
            "confirm that the skills most central to your current "
            "positioning are prominent rather than buried",
        ],
        "patterns": [
            r"\bendorse(?:d|ment|ments|s)?\b",
            r"ordering\s+of\s+your\s+(?:top\s+)?skills",
            r"prioritiz(?:e|ing)\s+(?:the\s+)?skills",
            r"front[-\s]of[-\s]list",
            r"prominent\s+rather\s+than\s+buried",
            r"(?:order|reorder|rearrange)\s+(?:your\s+)?(?:top\s+)?skills",
            r"skills?\s+(?:display\s+)?order",
            r"(?:request|solicit|ask(?:ing)?\s+for|obtain|seek|secure|"
            r"gather|collect)\s+(?:\w+\s+){0,3}recommendations?",
            r"recommendations?\s+(?:are|is|were|was)\s+(?:not\s+)?"
            r"(?:visible|present|absent|missing)",
            r"your\s+recommendations?\b",
            r"\bnew\s+recommendations?\b",
        ],
    },
    {
        "id": "F8b-excluded-subject-mention",
        "tier": "REVIEW",
        "what": "The bare word 'recommendation(s)' anywhere in client text",
        "why": "The word is ambiguous in this deliverable: it may be the "
               "excluded LinkedIn feature, or the ordinary advice sense ('the "
               "recommendations in this card'). REVIEW so a legitimate use "
               "does not read as a breach — but every hit is worth a look, "
               "because the feature sense must never ship.",
        "exemplar": None,
        "patterns": [
            r"\brecommendations?\b",
        ],
    },
    {
        "id": "F9-mechanism-quantified",
        "tier": "REVIEW",
        "what": "A documented mechanism with a magnitude attached",
        "why": "Ruling 3: mechanism citable, effect size never. Fires when a "
               "mechanism phrase sits within ~120 characters of a figure, "
               "which is a proximity heuristic — read the hit.",
        "exemplar": None,
        "patterns": [
            r"(?:member\s+embedding|semantically\s+embedded|post's\s+"
            r"representation|retrieval\s+system)"
            r"[^.]{0,120}?\d",
            r"\d[^.]{0,120}?"
            r"(?:member\s+embedding|semantically\s+embedded|retrieval\s+"
            r"system)",
        ],
    },
    {
        "id": "F10-soft-causal",
        "tier": "REVIEW",
        "what": "Hedged causal language between behavior and result",
        "why": "Most of the twenty v3 breaches were hedged rather than flat, "
               "so the hedges are where the volume is. This family will also "
               "fire on legitimate signal-legibility prose — read the hits, "
               "do not treat the count as a score.",
        "exemplar": None,
        "patterns": [
            r"\b(?:should|will|tends?\s+to|likely\s+to|helps?\s+to)\s+"
            r"(?:\w+\s+){0,3}"
            r"(?:reach|visibility|impressions|exposure|engagement|audience)",
            r"\bas\s+(?:you|your)\s+\w+(?:\s+\w+){0,3},?\s+"
            r"(?:you|your)\s+\w+\s+will",
            r"\bcompounds?\b",
            r"\bsnowball",
            r"\bmomentum\b",
            # 2026-08-18 dump read.
            r"(?:are|is)\s+the\s+result\s+of",
            r"goals\s+are\s+served",
        ],
    },
    {
        "id": "F11-population-benchmark",
        "tier": "REVIEW",
        "what": "The member compared against an invented population baseline",
        "why": "2026-08-18 dump read: multiple runs asserted comparisons "
               "('well above what most active LinkedIn users produce', 'a "
               "posting practice most professionals never reach') against a "
               "population the corpus contains no data on. REVIEW because "
               "some comparative phrasing is legitimate calibration language "
               "— read the hit and ask what data the baseline could rest on.",
        "exemplar": "well above what most active LinkedIn users produce",
        "also_catches": [
            "a posting practice that most professionals never reach",
            "Most LinkedIn users, even active ones, engage primarily "
            "through reactions",
            "well above most professional profiles",
        ],
        "patterns": [
            r"\babove\s+what\s+most\b",
            r"\bmost\s+(?:active\s+)?linkedin\s+users\b",
            r"\bmost\s+professionals?\b",
            r"\bmost\s+professional\s+profiles\b",
            r"\bmost\s+active\s+users\b",
        ],
    },
    {
        "id": "F12-derived-window-share",
        "tier": "REVIEW",
        "what": "A computed share of the window presented as a figure",
        "why": "2026-08-18 dump read: agent-computed percentages ('zero-post "
               "weeks account for 12% of the trailing year') pass the "
               "prose-number gate because small integers are structurally "
               "allowed, so this sweep is the only detector for them. Claims "
               "rule 6 forbids derived arithmetic; run 4 of the 08-18 sweep "
               "also derived it WRONG ('12 zero-post weeks... represent "
               "12%'). REVIEW because a supplied rate can be phrased this "
               "way legitimately — check the figure against the inputs.",
        "exemplar": "zero-post weeks account for only 12% of the trailing "
                    "year",
        "also_catches": [
            "which represent 12% of the trailing 52 weeks",
        ],
        "patterns": [
            r"\d{1,2}\s?%\s+of\s+(?:the\s+)?(?:trailing\s+|last\s+)?"
            r"(?:year|weeks?|window|months?|days?)",
            r"(?:account(?:s|ing)?\s+for|represent(?:s|ing)?)\s+"
            r"(?:only\s+)?(?:about\s+|roughly\s+|nearly\s+)?\d{1,2}\s?%",
        ],
    },
]

# Informational rather than a failure: the numeric form of the Ruling 2 breach
# (impressions/post, followers, engagement-rate milestone targets) is
# explicitly OUT of ORPHEUS-134's scope and gated on the team's milestone
# decision. Reported so the sweep tells the whole truth about what the run
# produced, and clearly separated so it never blocks 134's acceptance.
OUTCOME_TARGET_KEYS = ("impressions_per_post", "followers", "engagement_rate")


def _compiled() -> list[dict]:
    out = []
    for fam in FAMILIES:
        out.append({
            **fam,
            "compiled": [
                re.compile(p, re.IGNORECASE) for p in fam["patterns"]
            ],
        })
    return out


COMPILED = _compiled()


# ============================================================
# The sweep
# ============================================================

def sweep(strings: list[tuple[str, str]]) -> list[dict]:
    """Flag every (surface, family, matched text) hit across all strings."""
    hits: list[dict] = []
    for surface, text in strings:
        if not text:
            continue
        for fam in COMPILED:
            for rx in fam["compiled"]:
                for m in rx.finditer(text):
                    hits.append({
                        "family": fam["id"],
                        "tier": fam["tier"],
                        "what": fam["what"],
                        "surface": surface,
                        "match": m.group(0).strip(),
                        "context": _context(text, m.start(), m.end()),
                    })
    return hits


def _context(text: str, start: int, end: int, width: int = 90) -> str:
    """The matched span with surrounding prose, so a hit is readable alone."""
    a = max(0, start - width)
    b = min(len(text), end + width)
    prefix = "..." if a > 0 else ""
    suffix = "..." if b < len(text) else ""
    return f"{prefix}{text[a:b].strip()}{suffix}"


def self_test() -> list[str]:
    """Every family with an exemplar must catch its own exemplar.

    This is the guard that keeps the sweep honest. A pattern edit that stops
    catching the breach the pattern exists for should fail here, loudly,
    before anybody reads a clean verdict off this tool.
    """
    failures: list[str] = []
    for fam in COMPILED:
        # The original v3 exemplar plus every phrasing a later dump read
        # taught the family (`also_catches`, added 2026-08-18). Both are
        # pinned the same way: a pattern edit that unlearns any of them
        # fails loudly.
        probes = ([fam["exemplar"]] if fam["exemplar"] else []) + list(
            fam.get("also_catches") or []
        )
        for probe in probes:
            caught = any(rx.search(probe) for rx in fam["compiled"])
            if not caught:
                failures.append(
                    f"{fam['id']} does NOT catch its own exemplar: "
                    f"{probe[:80]!r}"
                )
    # And the inverse: prose that is deliberately inside the permitted
    # registers must NOT trip the HIGH tier. A detector that flags everything
    # is as useless as one that flags nothing, and this is where over-broad
    # patterns get caught.
    permitted = [
        "A headline that names your domain gives the retrieval system "
        "something specific to match against.",
        "A recruiter scanning this page could not tell which of your two "
        "fields you want to be hired in.",
        "Your About section does not connect your past experience to your "
        "current work.",
        "You published an average of 1.5 posts a week over the past year.",
        "Active in 11 of the last 52 weeks.",
        "No original posts recorded during the evaluation period.",
        # These two are the precision probes that forced F7b and F8b to exist.
        # Both were HIGH-tier false positives on the first draft of this
        # table. If a later pattern edit re-promotes either shape to HIGH,
        # this test fails and says so.
        "You do not have a call to action in your About section.",
        "The recommendations in this card are ordered by leverage.",
        # 2026-08-18: the F5 idiom false positive from run 3 of the 08-17
        # sweep, and two observation-only rhythm items in the register the
        # prompt's Claims rule 7 permits — the expanded F6 must not eat them.
        "This headline doubles as a positioning statement for the profile.",
        "Did you publish at least twice this week?",
        "Review whether your posting cadence held through the month.",
    ]
    for text in permitted:
        for fam in COMPILED:
            if fam["tier"] != "HIGH":
                continue
            for rx in fam["compiled"]:
                if rx.search(text):
                    failures.append(
                        f"{fam['id']} false-positives on permitted prose "
                        f"({rx.pattern!r} matched {text[:60]!r})"
                    )
    return failures


# ============================================================
# Env / fetch (same resolution as regenerate_report.py)
# ============================================================

def _load_env(need_anthropic: bool) -> None:
    for env_path in (REPO_ROOT / "backend" / ".env", REPO_ROOT / ".env"):
        if not env_path.exists():
            continue
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key, value = key.strip(), value.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = value
    required = ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"]
    if need_anthropic:
        required.append("ANTHROPIC_API_KEY")
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        sys.exit(f"Missing required env vars: {', '.join(missing)} "
                 f"(checked environment, backend/.env, .env)")


def _resolve_job_id(supabase, prefix: str) -> str:
    if len(prefix) >= 36:
        return prefix
    rows = (
        supabase.table("jobs").select("id,created_at")
        .order("created_at", desc=True).execute()
    ).data or []
    matches = [r["id"] for r in rows if r["id"].startswith(prefix)]
    if not matches:
        sys.exit(f"No job id starts with {prefix!r}.")
    if len(matches) > 1:
        sys.exit(f"Ambiguous prefix {prefix!r}: {', '.join(matches)}")
    return matches[0]


def _fetch_context(supabase, job_id: str) -> dict:
    job = (
        supabase.table("jobs").select("*").eq("id", job_id).single().execute()
    ).data
    client_row = (
        supabase.table("clients")
        .select("*, advisors!inner(is_individual, narrative_config)")
        .eq("id", job["client_id"]).single().execute()
    ).data
    q_row = (
        supabase.table("questionnaire_responses").select("answers")
        .eq("client_id", job["client_id"]).single().execute()
    ).data
    ingested = (
        supabase.table("ingested_data")
        .select("zip_data,xlsx_data,quality_report")
        .eq("job_id", job_id).single().execute()
    ).data
    scores = (
        supabase.table("scores").select("*").eq("job_id", job_id)
        .single().execute()
    ).data
    narratives = (
        supabase.table("narratives").select("*").eq("job_id", job_id).execute()
    ).data or []
    return {
        "job": job,
        "client_row": client_row,
        "questionnaire": (q_row or {}).get("answers") or {},
        "ingested": ingested,
        "scores": scores,
        "narratives": narratives,
    }


def stored_strings(ctx: dict) -> list[tuple[str, str]]:
    """Reassemble what the member actually read, from the stored rows.

    Three storage surfaces, because the merge fans out at write time:
      - `narratives` rows carry the four dimension narratives and the
        cheat sheet (as a JSON blob under section='cheat_sheet').
      - `scores.dimensions` carries the per-dimension summaries and every
        sub-dimension slot, merged in by the processor.

    `edited_text` wins over `generated_text` where an admin has overridden a
    section, because the point of the control is the text a human saw — not
    the text the model produced.
    """
    out: list[tuple[str, str]] = []
    for row in ctx["narratives"]:
        section = row.get("section")
        text = row.get("edited_text") or row.get("generated_text") or ""
        if section == "cheat_sheet":
            try:
                cs = json.loads(text or "{}")
            except json.JSONDecodeError:
                out.append(("cheat_sheet:UNPARSEABLE", text))
                continue
            for i, p in enumerate(cs.get("priorities", [])):
                out.append((f"cheat_sheet.priorities[{i}]",
                            f"{p.get('title', '')} {p.get('action', '')}"))
            for sec in cs.get("rhythm", []):
                for i, item in enumerate(sec.get("items", [])):
                    out.append(
                        (f"cheat_sheet.rhythm[{sec.get('cadence')}][{i}]",
                         item)
                    )
            for i, m in enumerate(cs.get("milestones", [])):
                out.append((f"cheat_sheet.milestones[{i}]",
                            f"{m.get('value', '')} {m.get('label', '')}"))
        else:
            out.append((f"section:{section}", text))

    dims = (ctx["scores"].get("dimensions") or {}).get("dimensions", [])
    for dim in dims:
        if dim.get("summary"):
            out.append((f"summary:{dim.get('name')}", dim["summary"]))
        for sub in dim.get("sub_dimensions", []):
            for slot in ("summary", "best_practices"):
                if sub.get(slot):
                    out.append(
                        (f"{dim.get('name')}/{sub.get('name')}.{slot}",
                         sub[slot])
                    )
            for i, bullet in enumerate(sub.get("improvements") or []):
                out.append(
                    (f"{dim.get('name')}/{sub.get('name')}"
                     f".improvements[{i}]", bullet)
                )
    return out


# ============================================================
# Reporting
# ============================================================

def _print_hits(hits: list[dict], label: str) -> tuple[int, int]:
    high = [h for h in hits if h["tier"] == "HIGH"]
    review = [h for h in hits if h["tier"] == "REVIEW"]
    print(f"  {label}: {len(high)} HIGH, {len(review)} REVIEW")
    for tier, group in (("HIGH", high), ("REVIEW", review)):
        if not group:
            continue
        print(f"    --- {tier} ---")
        by_family: dict[str, list[dict]] = {}
        for h in group:
            by_family.setdefault(h["family"], []).append(h)
        for fam_id in sorted(by_family):
            group_hits = by_family[fam_id]
            print(f"    [{fam_id}] {group_hits[0]['what']} "
                  f"({len(group_hits)} hit(s))")
            for h in group_hits:
                print(f"      {h['surface']}")
                print(f"        matched: {h['match']!r}")
                print(f"        context: {h['context']}")
    return len(high), len(review)


def _report_outcome_targets(milestone_targets) -> None:
    flagged = [t for t in milestone_targets if t.key in OUTCOME_TARGET_KEYS]
    if not flagged:
        print("  outcome-target milestones: none in this run")
        return
    print(f"  outcome-target milestones: {len(flagged)} "
          f"(INFORMATIONAL — out of ORPHEUS-134's scope)")
    for t in flagged:
        print(f"    {t.value:>10}  {t.label}")
    print("    These are the numeric form of the Ruling 2 breach and are "
          "deliberately")
    print("    excluded from 134 pending the team's milestone decision. Not "
          "a failure here.")


def _dump(out_dir: Path, name: str, strings: list[tuple[str, str]]) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.txt"
    lines = [
        f"# {name}",
        "",
        "Every client-facing string, in generation order. This file is the "
        "acceptance",
        "artifact — read it. The flag report only says where to look first.",
        "",
    ]
    for surface, text in strings:
        lines.append(f"--- {surface} " + "-" * max(0, 68 - len(surface)))
        lines.append(text or "(empty)")
        lines.append("")
    path.write_text("\n".join(lines))
    return path


# ============================================================
# Main
# ============================================================

async def run(args) -> int:
    failures = self_test()
    if failures:
        print("DETECTOR SELF-TEST FAILED — refusing to sweep.")
        print("A detector that cannot catch the breaches it was written for "
              "would report")
        print("a false clean. Fix the patterns before trusting any verdict.")
        for f in failures:
            print(f"  - {f}")
        return 3
    print(f"Detector self-test passed "
          f"({len(FAMILIES)} families, "
          f"{sum(len(f['patterns']) for f in FAMILIES)} patterns).")

    if args.self_test_only:
        return 0

    from supabase import create_client  # local: not needed for --self-test

    _load_env(need_anthropic=args.runs > 0)
    supabase = create_client(
        os.environ["SUPABASE_URL"], os.environ["SUPABASE_SERVICE_KEY"]
    )

    job_id = _resolve_job_id(supabase, args.job_id)
    ctx = _fetch_context(supabase, job_id)
    job = ctx["job"]
    stamp = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    out_dir = REPO_ROOT / f"sweep_{job_id[:8]}_{stamp}"

    print()
    print(f"Job {job_id}  ({ctx['client_row'].get('display_name')})")
    print(f"  created  {job.get('created_at')}")
    print(f"  status   {job.get('status')}")
    print(f"  stored   {ctx['scores'].get('total_score')} / "
          f"{ctx['scores'].get('band')}")
    print("  THIS SCRIPT NEVER WRITES. Reads and generates in memory only.")
    print()

    control_high = None
    if args.control:
        print("=" * 66)
        print("CONTROL — the stored delivered text")
        print("=" * 66)
        print("This text is known to contain the v3 breaches. The detector "
              "MUST light")
        print("up here; if it does not, its verdict on fresh text means "
              "nothing.")
        print()
        strings = stored_strings(ctx)
        print(f"  {len(strings)} client-facing strings recovered from storage")
        hits = sweep(strings)
        control_high, _ = _print_hits(hits, "stored text")
        path = _dump(out_dir, "control_stored_text", strings)
        print(f"  full text -> {path.relative_to(REPO_ROOT)}")
        print()
        if control_high == 0:
            print("  CONTROL FAILED: zero HIGH hits on text known to breach.")
            print("  Either the stored rows were already corrected, or the "
                  "sweep is broken.")
            print("  Do not read a clean result off the fresh runs until this "
                  "is understood.")
            print()

    if args.runs <= 0:
        print("No generations requested (--runs 0). Done.")
        return 0

    print("=" * 66)
    print(f"FRESH GENERATIONS — {args.runs} run(s), "
          f"~${args.runs * COST_PER_RUN_USD:.2f} total")
    print("=" * 66)

    zip_data = ZipData.model_validate(ctx["ingested"]["zip_data"])
    xlsx_data = (
        XlsxData.model_validate(ctx["ingested"]["xlsx_data"])
        if ctx["ingested"].get("xlsx_data") else None
    )
    quality_report = DataQualityReport.model_validate(
        ctx["ingested"].get("quality_report") or {}
    )

    dim1, dim4 = {}, {}
    for dim in (ctx["scores"].get("dimensions") or {}).get("dimensions", []):
        if dim.get("name") == RUBRIC_DIMENSIONS[0]:
            dim1 = {s["name"]: int(round(float(s["score"])))
                    for s in dim.get("sub_dimensions", [])}
        elif dim.get("name") == RUBRIC_DIMENSIONS[1]:
            dim4 = {s["name"]: int(round(float(s["score"])))
                    for s in dim.get("sub_dimensions", [])}
    if not dim1 or not dim4:
        sys.exit("Stored scores row is missing rubric sub-dimensions; cannot "
                 "re-score without spending rubric calls. Use a job scored "
                 "after ORPHEUS-21.")

    recorded = (job.get("config_snapshot") or {}).get("ref_date")
    ref_date = (
        date.fromisoformat(recorded) if recorded else resolve_ref_date(zip_data)
    )
    scoring_output = run_scoring(
        zip_data=zip_data,
        xlsx_data=xlsx_data,
        dim1_rubric_scores=dim1,
        dim4_rubric_scores=dim4,
        ref_date=ref_date,
        photo_present_override=job.get("oidc_photo_present"),
    )
    milestone_targets = build_milestone_targets(scoring_output)
    narrative_config = (
        (ctx["client_row"].get("advisors") or {}).get("narrative_config") or {}
    )

    from anthropic import Anthropic
    anthropic_client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    totals = []
    for i in range(1, args.runs + 1):
        print()
        print(f"--- run {i} of {args.runs} " + "-" * 42)
        result = await generate_narratives(
            client=anthropic_client,
            scoring_output=scoring_output,
            questionnaire=ctx["questionnaire"],
            zip_data=zip_data,
            narrative_config=narrative_config,
            quality_report=quality_report,
        )
        if result.prose_gate_degraded:
            print(f"  NOTE prose-gate degraded (ORPHEUS-131): "
                  f"{result.prose_gate_violations}")
        strings = prose_numbers.client_facing_strings(result)
        hits = sweep(strings)
        high, review = _print_hits(hits, f"run {i}")
        _report_outcome_targets(milestone_targets)
        path = _dump(out_dir, f"run_{i:02d}", strings)
        print(f"  full text -> {path.relative_to(REPO_ROOT)}")
        totals.append((high, review, len(strings)))

    print()
    print("=" * 66)
    print("SUMMARY")
    print("=" * 66)
    for i, (high, review, n) in enumerate(totals, start=1):
        verdict = "no known breach" if high == 0 else "BREACH"
        print(f"  run {i}: {high} HIGH, {review} REVIEW "
              f"over {n} strings — {verdict}")
    clean = sum(1 for h, _, _ in totals if h == 0)
    print()
    print(f"  {clean} of {len(totals)} runs produced no HIGH-tier hit.")
    if control_high is not None:
        print(f"  control (known-bad stored text): {control_high} HIGH — "
              f"detector {'is live' if control_high else 'DID NOT FIRE'}")
    print()
    print("  A clean sweep is NOT acceptance. It means no breach family we "
          "already")
    print("  know about re-appeared. The 2026-07-27 lesson: a clean run "
          "proves nothing")
    print("  about a stochastic generator. Read the dumped text in "
          f"{out_dir.name}/,")
    print("  and record what you read on ORPHEUS-134 — that reading is the "
          "acceptance")
    print("  evidence, not this exit code.")
    return 0 if clean == len(totals) else 1


def main() -> int:
    ap = argparse.ArgumentParser(
        description="ORPHEUS-134/137 claims-layer acceptance sweep "
                    "(read-only; never writes)."
    )
    ap.add_argument("job_id", nargs="?", default=None,
                    help="Job id or unique prefix, e.g. b03ca0f5.")
    ap.add_argument("--runs", type=int, default=0,
                    help="Fresh generations to sweep (~$0.10 each). "
                         "Default 0.")
    ap.add_argument("--control", action="store_true",
                    help="Also sweep the job's stored delivered text, which "
                         "validates the detector against known breaches.")
    ap.add_argument("--self-test", dest="self_test_only", action="store_true",
                    help="Run the detector self-test and exit. No DB, no API.")
    args = ap.parse_args()

    if not args.self_test_only and not args.job_id:
        ap.error("job_id is required unless --self-test is given.")
    if not args.self_test_only and args.runs <= 0 and not args.control:
        ap.error("nothing to do: pass --runs N, --control, or --self-test.")

    return asyncio.run(run(args))


if __name__ == "__main__":
    sys.exit(main())
