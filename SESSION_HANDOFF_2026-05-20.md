# Session Handoff — 2026-05-20

Jump-in doc for the next Claude session. Replaces both `SESSION_HANDOFF_2026-05-19.md` and `SESSION_HANDOFF_2026-05-19_part2.md` — all threads from both are closed in code, deployed, or moved into CLAUDE.md "Decisions Made". Two prior handoffs are retired in this commit because the part-2 commit (`9676b4b`) declared retirement of the first but the file was never actually deleted in the working tree — minor process miss, surfaced here so future wraps tighten the verification check.

This session was meta-work, not engineering: documentation strategy for keeping Josh, Andrew, and Tim in sync, plus the Signal Score / Forward Brief ownership clarification that lands alongside it. No Plane ticket — coordination work isn't ticketed in the existing convention.

---

## Status at a glance

| Ticket | Title | Status |
|---|---|---|
| ORPHEUS-47 | Frontend: stand up vitest + RTL | ✅ Done (from prior session). |
| ORPHEUS-21 | Backend: Extend SubDimensionScore with narrative fields | ⏸ Hold pending Andrew's Forward Brief revisions. |
| ORPHEUS-22 | Backend: Dimension-level band classification | ⏸ Needs Andrew's product call. |
| ORPHEUS-25 | Cloud Supabase + prod LinkedIn OIDC provider | ⏳ Backlog. Ops/config. Gates 44. |
| ORPHEUS-31 | `/admin` stopgap (email-allowlisted) | ⏳ Forward-Brief-safe. Medium. |
| ORPHEUS-43 | Pin Railway build command in source | ⏳ Forward-Brief-safe. Smallest. **Top recommendation for next session** (carried from prior handoff). |
| ORPHEUS-44 | Live e2e walkthrough of invite + advisor flow | ⏳ Gated on 25. |
| ORPHEUS-45 | Advisor admin UI: 'Edit' action on client list rows | ⏳ Forward-Brief-safe. UX. Rename-only is smallest scope. |
| ORPHEUS-48 | Multi-tenant branding | ⏸ Deferred. |
| ORPHEUS-40 / 41 / 42 | Stripe, disconnect, account mgmt | ⏸ Beta-deferred. |

No tickets shipped this session. No new tickets created.

---

## What this session actually shipped

### Signal Score / Forward Brief ownership clarified

Andrew owns the framework's **design** — what is measured, how it's measured, dimensions, weights, bands, sub-dimension rubrics, score-to-band mapping. He is SME and framework author. Josh owns the **product application** of the design — whether and how it lands in product, what surfaces to the client, when, in what form.

Three places in CLAUDE.md were edited to lock the split:

- Josh's "Owns" list (People & roles): new bullet for *"Signal Score and Forward Brief as products — the decision of whether and how Andrew's framework design lands in the product (what surfaces to the client, when, in what form). Andrew is consulted as SME and framework author."*
- Andrew's "Owns" list (People & roles): the first bullet now reads *"Signal Score and Forward Brief framework design — what is measured, how it's measured, dimensions, weights, bands, sub-dimensions, rubrics, score-to-band mapping. Andrew is SME and framework author; Josh owns the product application of the design."*
- "Decision routing for AI sessions" list: replaced the single `Scoring framework, narrative content, advisor practice → Andrew` bullet with three more-precise bullets — framework design → Andrew, product application → Josh, narrative content and advisor practice → Andrew.

The prior framing risked conflating "the design is sound" with "this is how we should build it in product." Andrew's authority over substantive product UX for non-Signal-Score surfaces is preserved by the unchanged "Product UX" bullet.

### Shared canon adopted

Two-doc structure living in the Ess3 shared drive at **Orpheus Social > 06_Operations > Shared Canon** ([folder](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g)):

- **[Orpheus — State of the Moment](https://docs.google.com/document/d/1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA/edit)** — daily-refreshed snapshot. Includes a "For Tim — Weekly Summary" block at the top that's refreshed only on Mondays (Tim's read cadence is weekly). Sections: For Tim, Sprint focus, Shipped in last 24h, In flight (per person), Blocked / open threads, Legal & Compliance (rich enough for Josh's product decisions even though Tim reads weekly), Thinking out loud (per person — pre-decision ideas live here, graduate to Decision Log when locked).
- **[Orpheus — Decision Log](https://docs.google.com/document/d/1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI/edit)** — append-only, reverse-chronological. Template per entry: date, title, decider(s), Decision, Rationale, Implications for product (required even when the decider isn't Josh), Source, Follow-ups. Seeded with two entries today: (1) Signal Score ownership clarification, (2) Shared canon adoption.

The canon is the new sync surface across Josh's, Andrew's, and Tim's distributed Claude sessions. Engineering canon stays in the repo. Cross-stakeholder decisions — Andrew's framework iterations, Tim's legal/compliance moves — now have a discoverable home.

Reading patterns:
- **Josh + Andrew:** daily, both docs, at session start.
- **Tim:** weekly (Monday), scans the "For Tim" block at the top of State of the Moment.

### Skills extended

Edits to `orpheus-session-start` and `orpheus-session-wrap` so future sessions read and refresh the canon as part of their existing rituals. Drafted in `outputs/skill_updates_canon_2026-05-20.md` during the session; Josh applied them to the skill files in-session.

- **Wrap:** new step between "Write SESSION_HANDOFF" and "Retire previous handoff" — refresh the State of the Moment (preserve other people's "Thinking out loud" entries; only refresh "For Tim" on Mondays) and append any session decisions to the Decision Log. Drive doc IDs added to the facts section. Verification list gains a canon-currency check.
- **Start:** new step in "The quick check" reads both docs at session open. New "Canon drift" subsection in Drift detection catches decisions logged between sessions that the SESSION_HANDOFF wouldn't see. Catch-up mode output gets a new "Cross-stakeholder updates since the last handoff" item between "What's in flight" and "Recommended next."

### Misplaced-folder cleanup

First attempt at the canon folder went inside Andrew's personal "Orpheus Social" Drive folder rather than the shared drive. Folder ID `16XzHm-yXLGPY6C_0fUd5kJPjcjQoA8FR`. Josh deleted in the Drive UI this session, then I recreated the canon under `Ess3 > Orpheus Social > 06_Operations > Shared Canon`. The Johnny-Decimal taxonomy of the shared drive was preserved — the canon sits as a sibling of Tools and Vendors inside the Operations category (cross-functional coordination is what 06 is for).

### CLAUDE.md "Decisions Made" entry

A single dated entry capturing both the ownership clarification and the canon adoption — they shipped together and the entry is wide enough to cover both.

---

## Known gaps + follow-ups

1. **Drive MCP is read-only for Google Doc *content* edits.** The Cowork-exposed `mcp__c97c6e0b-...` Drive MCP has `create_file`, `read_file_content`, `download_file_content`, `copy_file`, `search_files`, `get_file_metadata`, `list_recent_files`, `get_file_permissions` — but no `update_file_content` or equivalent. This affects the canon-refresh step in the wrap skill: future Claude sessions can read existing canon content and append new Decision Log entries via create-new-doc patterns, but **in-place State of the Moment refreshes need a different tool surface or a manual UI step**. For today, the State of the Moment INDEX section's "Standup logs" line (now known to be `Orpheus Social > 07_Meetings > Standups`) is a manual edit Josh can do in the doc UI. If a future session has a Drive MCP variant that exposes an update tool, the wrap skill's canon-refresh step works as written.

2. **SESSION_HANDOFF_2026-05-19.md was not retired in the part-2 commit despite the commit's stated intent.** Surfaced this session. Both files are retired in today's commit. Future wrap sessions should run the verification check ("the new SESSION_HANDOFF exists and the previous one is deleted") more strictly — `git status` after staging should show both an `add` and a `delete`, not just an `add`.

3. **No live e2e of the cross-stakeholder canon model yet.** Andrew and Tim haven't actually used it through their own Claude sessions. The model is scaffolded and the skills are wired, but the first cross-stakeholder use will be the real validation. Andrew picks up async — his first session reading the canon is the e2e test.

4. **Skill-edit handoff doc is transient.** `outputs/skill_updates_canon_2026-05-20.md` exists in the Cowork outputs directory (not the repo). It captured the before/after blocks for the two skill files. Now that Josh has applied them, the doc can be discarded — it's not authoritative. Listed here so the next session doesn't go hunting for it.

---

## Pickup plan for next session

Engineering pickup unchanged from the prior handoff: **ORPHEUS-43** (Pin Railway build command in source) remains the top recommendation. Smallest scope, ~1 commit, Forward-Brief-safe.

Alternatives unchanged: ORPHEUS-45 (Edit action on client list rows), ORPHEUS-31 (`/admin` stopgap), or stand up the next vitest test (`SmartIndexRedirect` / `AdvisorRoute` / `InviteCallbackPage` are the obvious candidates).

The post-canon-update `orpheus-session-start` skill should now read the State of the Moment and Decision Log alongside the handoff at every start — the first run with the new skill in place is also a validation that the canon-drift detection works as intended.

---

## Caveats / things that will bite

1. **ORPHEUS-25 still gates the live e2e walks.** Unchanged from prior handoff.
2. **Andrew's Forward Brief revisions are pending.** Hold on ORPHEUS-21, 22, 48 until they land.
3. **Sandbox can't run pytest** (PyPI blocked). Backend test execution still happens from Josh's terminal. Baseline: **173 pytest green** (unchanged this session — no backend touched).
4. **Sandbox can't push via SSH.** All `git push origin main` operations are manual from Josh's terminal.
5. **`.git/*.lock` files cannot be unlinked** from the sandbox. Use the standard `mv` pattern before each commit.
6. **Drive MCP is read-only for Doc content.** See "Known gaps" above. Affects the canon-refresh step in the wrap skill.

---

## State of the repo right now (end of session)

After this commit lands:

```
On branch main
Your branch is ahead of 'origin/main' by 1 commit (this handoff + the CLAUDE.md ownership/Decisions-Made updates).

Untracked:
  LinkedIn_BD_DPA_Review_2026-05-07.md
  Orpheus_Privacy_Policy_DRAFT_2026-05-07.{md,docx}
  Orpheus_Terms_of_Service_DRAFT_2026-05-07.{md,docx}
```

The five compliance drafts stay untracked, same posture as the prior handoff.

Both `SESSION_HANDOFF_2026-05-19.md` and `SESSION_HANDOFF_2026-05-19_part2.md` are retired in this commit.

Suggested push:

```bash
cd ~/git/orpheus && git push origin main
```

---

## Shared canon — quick reference for next session

- **Folder:** `1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g` ([Orpheus Social > 06_Operations > Shared Canon](https://drive.google.com/drive/folders/1EQi5XxgOPEFEx5kjhkdEn53F5slZSK-g))
- **State of the Moment doc ID:** `1N7mbJztfOAABNzRANvWU5K_D9And0dFz1_0n42Z8euA`
- **Decision Log doc ID:** `1cHIcyafWrzdlfdfF4BkVi8MbITyaB4Ii_DTvKLCRbOI`
- **Standup logs:** `Orpheus Social > 07_Meetings > Standups` (URL pending — Josh to confirm and paste into State of the Moment INDEX)
