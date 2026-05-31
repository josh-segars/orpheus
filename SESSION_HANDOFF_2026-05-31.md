# Session Handoff — 2026-05-31

Jump-in doc for the next Claude session. Retires `SESSION_HANDOFF_2026-05-30_part3.md` — its recommended pickup (ORPHEUS-43) shipped this session and the threads it described are all closed in code or have moved into CLAUDE.md "Decisions Made".

Single-ticket day. Smaller scope than the 2026-05-30 chain, no same-day follow-ups.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-43 | Pin Railway build command in source | ✅ Done. 3 commits (`120dccd`, `e77882f`, `f567b19`); two pivots before the final shape landed. Live: green redeploy on both Railway services. |
| ORPHEUS-22 | Server-side per-dimension band classification | ✅ Done last session (`f76b9d9`). |
| Prototype backport | ORPHEUS-51/52 HTML sync | ✅ Done last session (`9f137f9` + `b029253`). |
| ORPHEUS-52 | PortalNav identity cluster | ✅ Done two sessions ago (`d39a02a`). |
| ORPHEUS-51 | Signal Score hero restructure + per-band waveforms | ✅ Done three sessions ago (`9a363e5`). |
| ORPHEUS-21 | Backend: Extend SubDimensionScore with narrative fields | ⏸ Hold pending Andrew's Forward Brief revisions. Unchanged. |
| ORPHEUS-25 | Cloud Supabase + prod LinkedIn OIDC provider | ⏳ Backlog. Ops/config. Gates 44. |
| ORPHEUS-31 | `/admin` stopgap (email-allowlisted) | ⏳ Forward-Brief-safe. |
| ORPHEUS-44 | Live e2e walkthrough of invite + advisor flow | ⏳ Gated on 25. |
| ORPHEUS-45 | Advisor admin UI: 'Edit' action on client list rows | ⏳ Forward-Brief-safe. UX. |
| ORPHEUS-48 | Multi-tenant branding | ⏸ Deferred. |
| ORPHEUS-40 / 41 / 42 | Stripe, disconnect, account mgmt | ⏸ Beta-deferred. |

No other tickets touched this session.

---

## What this session shipped

### ORPHEUS-43 — Railway build pinned in source (3 commits, two pivots)

Filed 2026-05-13 after the ORPHEUS-38 deploy crashed with `ModuleNotFoundError: No module named 'pydantic_settings'`. Workaround at the time was a manual Build Command override on both Railway services (`pip install -r backend/requirements.txt`), brittle because it lived in the dashboard rather than source control.

**Final shape.** `backend/requirements.txt` is promoted to repo-root `requirements.txt` (single canonical Python deps file at the standard location). Railpack's Python provider auto-detects the root file and runs `pip install -r requirements.txt` against it. Manual override cleared on both services; both come up green on a fresh build with the explicit pip install step in build logs. `nixpacks.toml` deleted as vestigial.

**Commit history (preserved as a learning trace rather than collapsed):**

- **`120dccd`** — first attempt at the ticket's option 1 (railpack.json). Pinned `pip install -r backend/requirements.txt` under the `python` provider via `steps.install.commands`. Same commit deleted the *existing stale* repo-root `requirements.txt` (it was an outdated copy missing `pydantic-settings`, `python-multipart`, `PyJWT`, `cryptography`, `pytest*`) and the vestigial `nixpacks.toml`. Also rolled in a recompressed-PNG refresh of `assets/images/wave-{1-5}-*.png` and a restoration of the `frontend/src/assets/wave-{1-5}-*.png` mirrors that Josh had deleted in the working tree pre-session (`SignalScorePage.tsx` imports them — would have broken the Vite build). **Build failed:** `failed to solve: process "pip install -r backend/requirements.txt" did not complete successfully: exit code: 1`.
- **`e77882f`** — first pivot. Hypothesized that overriding `steps.install.commands` dropped the auto-generated step's input layer, so `backend/requirements.txt` wasn't visible in the build container. Pivoted to ticket-endorsed option 2 in its literal form: deleted `railpack.json`, added root `requirements.txt` containing `-r backend/requirements.txt`. **Build failed again.** Diagnostic from Railway: "Railpack's Python install layer only copies the root requirements.txt file, so the -r backend/requirements.txt include directive cannot resolve when pip runs. The backend/ directory is not available at that point in the build."
- **`f567b19`** — second pivot. Promoted the real dep list to repo-root `requirements.txt` (canonical) and deleted `backend/requirements.txt`. Git recognized this as a 100% rename. After push, manual override cleared in Railway dashboard, both services green.

**Root cause of the original ticket's `ModuleNotFoundError`** turned out to be the *stale* root `requirements.txt` itself: it was committed before the project's Python deps grew, Railpack auto-detected it and installed the outdated list, and the dashboard override masked the issue by superseding what auto-detection saw. `120dccd` deleted that file (alongside `nixpacks.toml`); `f567b19` recreated it with the canonical full list.

**Implementer decisions locked** (captured on the Plane closing comment + CLAUDE.md):

- **Canonical Python deps live at repo root, not `backend/`.** Single source of truth; standard Python project layout. The `backend/` directory now contains only application code.
- **No railpack.json.** Tried it; overriding `steps.install` proved fragile because it also drops the provider's input-layer setup. Railpack's default Python detection against a root `requirements.txt` is the simpler, more durable pin.
- **Pivot history preserved in commits**, not collapsed. The repo log reads "tried railpack, didn't work; tried forwarder, didn't work; promoted to root" — that's the honest debugging trace and the path is clear if anyone audits the ticket later.

Also this session: doc refresh in CLAUDE.md (Active phase paragraph + Decisions Made entry + file-structure tree updated to show root `requirements.txt` + Railway env vars note revised), PRODUCT_CONTEXT.md (Railway deployment row), CREDENTIALS.md (Build command row).

### New tickets filed

None this session.

---

## Recommended pickup for next session

**ORPHEUS-21 (sub-dim narrative fields)** if Andrew's Forward Brief revisions have landed — the ORPHEUS-50 redesign's expandable sub-dim rows are already wired to receive `summary` / `best_practices` / `improvements` strings, so unblocking 21 fills the empty UI states with no contract change. Worth a check-in with Andrew before committing to it.

**Alternative pickups:**

- **ORPHEUS-45 (Edit action on client rows).** Concrete-but-small advisor UX win. Filed when ORPHEUS-39 shipped because there was no use case yet; Andrew or Tim using the advisor surface in anger would surface what "edit" should actually do.
- **ORPHEUS-31 (/admin stopgap).** Email-allowlisted internal page. Useful before the first real advisor session as a "look at any client's job by id" surface. Forward-Brief-safe.
- **Loading-flicker polish on the PortalNav cluster** (filed in 2026-05-30_part2's "alternative pickups", carried forward). Gate the name render on `useAdvisorClients` / `useJob` completion so advisor-on-client-job doesn't briefly show the advisor's own name. Trivial follow-up; only worth doing if it's been observed in practice.
- **"Prepared for [own name]" on `/advisor/clients`** (carry-forward). Tighten if it grates — hide the eyebrow when no `:jobId` is present.
- **CONVENTIONS.md update for same-day handoffs** (carry-forward from 2026-05-30_part3). The `_part2` / `_part3` pattern has held three weeks running. The retire-in-intro pattern works fine, but formalizing it in CONVENTIONS.md would mean the next fresh session reads the convention before reinventing it. *Today's single-ticket session didn't trigger the pattern, so the urgency is unchanged.*
- **`frontend/src/assets/waves.jpg` cleanup** (carry-forward from 2026-05-30_part2). One-line removal — the file is unreferenced post-ORPHEUS-51's band-keyed asset swap. Trivial; haven't been bothered enough yet.

---

## Caveats / things that will bite

1. **Build pin sensitivity.** Railpack's auto-detection now drives the Python install. Two things that would re-break it: (a) editing root `requirements.txt` to forward (`-r backend/...`) — won't resolve, same layer-scope issue we hit this session; (b) reintroducing `backend/requirements.txt` without keeping the root one in sync, then accidentally relying on the wrong one. Treat root `requirements.txt` as the only canonical source.
2. **Doc references to `backend/requirements.txt`** were updated in CLAUDE.md / PRODUCT_CONTEXT.md / CREDENTIALS.md this session. If any other doc or script still says `backend/requirements.txt`, it's now stale — check before relying on it.
3. **Sandbox can't run pytest** (PyPI blocked). Backend test baseline of ~180 green from ORPHEUS-22 is unverified this session — ORPHEUS-43 didn't touch backend tests so no expected change. Josh's terminal is the verification path if a number is needed.
4. **Sandbox can ship code commits directly** (proven again — 3 commits + 1 wrap commit from the sandbox this session). Only the `git push` step still requires Josh's terminal due to SSH egress. The `.git/objects/tmp_obj_*` warnings during commits are cosmetic (same EPERM family as `.git/*.lock`).
5. **`.git/*.lock` workaround still needed before each commit** (standard pattern). Re-encountered this session.
6. **Sandbox can't push via SSH.** Manual push from Josh's terminal.
7. **Vite build fails to clean `dist/` from the sandbox.** Unchanged; `tsc -b` alone is the right sandbox sanity check (ran clean this session for the wave-PNG mirror restoration).
8. **Vitest does run from the sandbox** (`npx vitest run`). Confirmed this session — 15 green (no test changes).
9. **Migration 013 still not yet applied to prod Supabase** (carry-forward from prior handoffs). Apply via Studio SQL Editor or `supabase db push`. Not gated by anything; just hasn't been done.
10. **ORPHEUS-25 still gates the live e2e walks.** Unchanged.
11. **Andrew's Forward Brief revisions are pending.** Holds ORPHEUS-21 / 48.
12. **HTML prototype drift lesson** (carry-forward from 2026-05-30_part3, still worth re-reading). When a ticket changes shared CSS in ways the prototype's markup depends on, the prototype update must land in the same session unless explicitly deferred. Didn't bite this session because ORPHEUS-43 touched no shared CSS.

---

## State of the repo right now (end of session)

After the handoff commit this skill produces:

```
On branch main
Your branch is ahead of 'origin/main' by 4 commits.
  (120dccd ORPHEUS-43: pin Railway build command via railpack.json)
  (e77882f ORPHEUS-43 follow-up: switch from railpack.json to root requirements.txt forwarder)
  (f567b19 ORPHEUS-43 follow-up #2: promote requirements.txt to repo root)
  (<handoff-sha> Session handoff: 2026-05-31. Retire 2026-05-30_part3.)

Untracked (intentionally — all in .gitignore):
  LinkedIn_BD_DPA_Review_2026-05-07.md
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
  Signal_Score_Dimensions_Reference_2026-05-20.md
```

Note: the three ORPHEUS-43 commits were already pushed mid-session so Josh could verify the green Railway deploy. The sandbox's `git fetch` is blocked (SSH egress), so `git status` from the sandbox still reads "up to date with origin/main" against a stale tracking ref. Local HEAD is actually 3 commits ahead of what the sandbox last saw on origin, plus the handoff commit makes 4. The push command below pushes the handoff commit (the three before it are already on origin/main).

`SESSION_HANDOFF_2026-05-30_part3.md` is retired in this commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Latest Decision Log entries:** 2026-05-29 Signal Score redesign + dark mode (ORPHEUS-50); 2026-05-29 band rename (ORPHEUS-49); 2026-05-20 ownership clarification + canon adoption. (No new Decision Log entry drafted this session — ORPHEUS-43 is pure deploy mechanics, Josh's call, not a cross-stakeholder decision.)
