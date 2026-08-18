"""Tests for the ORPHEUS-134/137 claims-layer acceptance sweep.

The sweep is a detector, and an untested detector is worse than none: it
produces confident clean verdicts on text nobody checked. These tests pin both
directions —

  * recall: the breach shapes from Andrew's v3 Part 1, plus paraphrases of
    them, must reach the HIGH tier;
  * precision: prose that sits inside the permitted registers must NOT reach
    the HIGH tier.

The precision half is the one that matters for review load. Two patterns in
the first draft of the family table fired HIGH on legitimate sentences ("You
do not have a call to action in your About section", "The recommendations in
this card are ordered by leverage"); both now live at REVIEW, where a human
reads them and decides. `test_permitted_prose_*` is what keeps a later pattern
edit from re-promoting them.

Neither half tests the *sweep's conclusion* about a real generation. That is
not testable here — it needs a live API call and a human reading the dump, and
it is recorded on ORPHEUS-134 rather than in CI.
"""

import pytest

from backend.scripts.claims_sweep import (
    COMPILED,
    FAMILIES,
    OUTCOME_TARGET_KEYS,
    _context,
    self_test,
    stored_strings,
    sweep,
)


def _hits(text: str, tier: str | None = None) -> list[str]:
    out = []
    for fam in COMPILED:
        if tier and fam["tier"] != tier:
            continue
        for rx in fam["compiled"]:
            if rx.search(text):
                out.append(fam["id"])
                break
    return out


# ============================================================
# The built-in self-test
# ============================================================

class TestDetectorSelfTest:
    """The script refuses to sweep when this fails. Keep it that way."""

    def test_self_test_passes(self):
        assert self_test() == []

    def test_every_high_family_carries_its_v3_exemplar(self):
        """A HIGH-tier family without an exemplar is unmoored — nothing pins it
        to the breach it was written for. REVIEW families are heuristics by
        construction and may omit one."""
        for fam in FAMILIES:
            if fam["tier"] == "HIGH":
                assert fam["exemplar"], (
                    f"{fam['id']} is HIGH tier but names no v3 exemplar"
                )

    def test_every_family_explains_itself(self):
        for fam in FAMILIES:
            assert fam["what"] and fam["why"], fam["id"]
            assert fam["tier"] in ("HIGH", "REVIEW"), fam["id"]
            assert fam["patterns"], fam["id"]


# ============================================================
# Recall
# ============================================================

V3_CRITICAL = [
    # 1 — Posting Presence threshold assertion.
    "places you well above the threshold where original content "
    "meaningfully contributes to a professional presence",
    # 2 — behavior to outcome.
    "this activity level is generating meaningful scale",
    "shows that the volume is translating into genuine audience exposure",
    # 3 — outcome promise against stated goals.
    "the behavioral foundation is already in place to support all of "
    "those outcomes",
    # 4 — visibility claim.
    "That breadth tends to support wider visibility across audience segments",
    "there is likely room to see that rate improve as topic focus sharpens",
    # 5 — effect size.
    "is likely the highest-leverage profile-level move available to you",
    "This is the single highest-leverage move available",
    # the two weekly-rhythm attribution instructions.
    "notice which angles generated the most response and let that inform "
    "the following week's framing",
    "note whether topic shifts correlate with changes in either metric",
    # the recommendations absence assertion.
    "Recommendations are not visible in your current profile and is one of "
    "the few structural elements currently absent",
]

PARAPHRASES = [
    "Posting consistently helps you get seen by more of the right people.",
    "The algorithm rewards regular activity.",
    "This gives your content a better chance of spreading.",
    "Expect roughly 30% more impressions once your cadence stabilises.",
    "A tighter topic focus drives more reach over time.",
    "Ask three colleagues for endorsements this month.",
    "Request recommendations from two senior colleagues.",
    "Review the ordering of your top skills.",
    "Commenting daily will double your visibility.",
    "Track which formats perform best and lean into them.",
]


# The phrasings the 08-17 and 08-18 sweep dump reads caught by hand while
# the patterns stayed silent (ORPHEUS-134 second pass). Each generation of
# missed phrasings gets appended here, so the detector's recall only ever
# ratchets forward.
RESIDUALS_2026_08_18 = [
    "Review your top-performing posts for common patterns and adjust your "
    "content approach accordingly.",
    "Notice which posts drew the most meaningful responses.",
    "Examine what made it travel further than the others.",
    "Note which openings, topics, or formats drew the most response and "
    "carry that forward.",
    "Which post traveled furthest, and what did it have in common with "
    "your other high-performing content?",
    "Use any significant shift as a prompt to examine what changed in your "
    "content or engagement pattern.",
    "Adjust your content mix if either is stalling.",
    "Study what your highest-performing posts have in common and apply "
    "those patterns more deliberately.",
    "A modest increase brings you to a cadence where your content is "
    "appearing in feeds more reliably.",
    "This is the lever most likely to pull in the readers whose attention "
    "matters most.",
    "Being thoughtful about where you comment could amplify what's already "
    "working.",
    "Consider prioritizing the skills most directly relevant to your "
    "current work.",
    "A more curated front-of-list could sharpen the first impression.",
]


class TestRecall:

    @pytest.mark.parametrize("text", V3_CRITICAL)
    def test_v3_critical_breach_reaches_high_tier(self, text):
        assert _hits(text, "HIGH"), f"not caught at HIGH: {text!r}"

    @pytest.mark.parametrize("text", PARAPHRASES)
    def test_paraphrased_breach_reaches_high_tier(self, text):
        """The v3 breaches were mostly hedged, and the next ones will be
        phrased differently again. Paraphrase recall is the closest thing to
        evidence that the patterns generalise past their exemplars."""
        assert _hits(text, "HIGH"), f"not caught at HIGH: {text!r}"

    @pytest.mark.parametrize("text", RESIDUALS_2026_08_18)
    def test_dump_read_residuals_reach_high_tier(self, text):
        """Loop closure for the 08-17/08-18 acceptance sweeps: everything a
        human read caught that the detector missed is now detector recall."""
        assert _hits(text, "HIGH"), f"not caught at HIGH: {text!r}"

    def test_review_families_catch_their_own_exemplars(self):
        """The 08-18 additions (population benchmarks, derived window
        shares) are REVIEW heuristics, but they still must fire on the
        text they were written for."""
        assert "F11-population-benchmark" in _hits(
            "well above what most active LinkedIn users produce", "REVIEW"
        )
        assert "F12-derived-window-share" in _hits(
            "zero-post weeks account for only 12% of the trailing year",
            "REVIEW",
        )


# ============================================================
# Precision
# ============================================================

PERMITTED = [
    # Signal-legibility register — explicitly permitted by Ruling 2.
    "A headline that names your domain gives the retrieval system something "
    "specific to match against.",
    "Your full profile is what builds the member embedding.",
    # Human-reader register — the preferred one.
    "A recruiter scanning this page could not tell which of your two fields "
    "you want to be hired in.",
    "A buyer landing here would not know what you sell.",
    # Observable gaps in ingested content — legitimate per Core rule 3, and
    # the score-calibration section depends on being able to say these.
    "Your About section does not connect your past experience to your "
    "current work.",
    "Your headline does not communicate a recognizable professional identity.",
    "You do not have a call to action in your About section.",
    "Your headline is missing a domain, so a reader cannot place you.",
    # Measured-signal citations — required by the prompt, not claims.
    "You published an average of 1.5 posts a week over the past year.",
    "Active in 11 of the last 52 weeks.",
    "No original posts recorded during the evaluation period.",
    # Plain behavioral instruction with no outcome attached.
    "Publish on a fixed weekly cadence: Monday, Wednesday, Friday.",
    "Leave a substantive reply on three posts a week.",
    # Advice-sense use of the ambiguous word.
    "The recommendations in this card are ordered by leverage.",
    # 2026-08-18: the F5 idiom false positive from the 08-17 sweep's run 3.
    "This headline doubles as a positioning statement for the profile.",
    # Observation-only review items in the register Claims rule 7 permits —
    # the expanded F6 must leave the permitted register alone.
    "Did you publish at least twice this week?",
    "Does this week's post name your domain?",
    "Review whether your posting cadence held through the month.",
]


class TestPrecision:

    @pytest.mark.parametrize("text", PERMITTED)
    def test_permitted_prose_does_not_reach_high_tier(self, text):
        assert _hits(text, "HIGH") == [], (
            f"false positive at HIGH on permitted prose: {text!r}"
        )

    def test_the_two_known_false_positives_stay_at_review(self):
        """Named explicitly, because both were HIGH in the first draft and the
        fix was to re-tier rather than to delete the pattern — the shapes are
        still worth a human read, they just are not breaches on their own."""
        absence = "You do not have a call to action in your About section."
        assert "F7b-absence-generic" in _hits(absence, "REVIEW")
        assert _hits(absence, "HIGH") == []

        advice = "The recommendations in this card are ordered by leverage."
        assert "F8b-excluded-subject-mention" in _hits(advice, "REVIEW")
        assert _hits(advice, "HIGH") == []


# ============================================================
# Sweep mechanics
# ============================================================

class TestSweepMechanics:

    def test_sweep_tags_every_hit_with_its_surface(self):
        strings = [
            ("section:Behavioral Signal Strength",
             "this activity level is generating meaningful scale"),
            ("cheat_sheet.priorities[0]",
             "Close the gap. This is the single highest-leverage move."),
        ]
        hits = sweep(strings)
        surfaces = {h["surface"] for h in hits}
        assert surfaces == {
            "section:Behavioral Signal Strength", "cheat_sheet.priorities[0]"
        }
        assert all(h["match"] and h["context"] for h in hits)

    def test_sweep_skips_empty_strings_without_raising(self):
        assert sweep([("summary:X", ""), ("summary:Y", None)]) == []

    def test_context_brackets_the_match_and_marks_truncation(self):
        text = "x" * 200 + "highest-leverage" + "y" * 200
        ctx = _context(text, 200, 216)
        assert "highest-leverage" in ctx
        assert ctx.startswith("...") and ctx.endswith("...")

    def test_context_does_not_mark_truncation_at_the_edges(self):
        ctx = _context("highest-leverage move", 0, 16)
        assert not ctx.startswith("...")
        assert not ctx.endswith("...")


class TestStoredStrings:
    """The control path. It reassembles the delivered text from three storage
    surfaces, so a shape change in any of them silently shrinks the control —
    which is exactly the failure that would make a broken detector look fine.
    """

    def _ctx(self) -> dict:
        return {
            "narratives": [
                {"section": "Behavioral Signal Strength",
                 "generated_text": "generated version"},
                {"section": "Profile Signal Clarity",
                 "generated_text": "machine text",
                 "edited_text": "the admin's rewrite"},
                {"section": "cheat_sheet", "generated_text": _CHEAT_SHEET},
            ],
            "scores": {
                "dimensions": {
                    "dimensions": [
                        {
                            "name": "Behavioral Signal Strength",
                            "summary": "dimension summary text",
                            "sub_dimensions": [
                                {
                                    "name": "Posting Presence",
                                    "summary": "sub summary",
                                    "best_practices": "sub best practices",
                                    "improvements": ["bullet one", "bullet two"],
                                },
                            ],
                        },
                    ]
                }
            },
        }

    def test_all_three_storage_surfaces_are_recovered(self):
        got = dict(stored_strings(self._ctx()))
        assert "section:Behavioral Signal Strength" in got
        assert "summary:Behavioral Signal Strength" in got
        assert "Behavioral Signal Strength/Posting Presence.summary" in got
        assert (
            "Behavioral Signal Strength/Posting Presence.best_practices" in got
        )
        assert (
            "Behavioral Signal Strength/Posting Presence.improvements[1]"
            in got
        )
        assert "cheat_sheet.priorities[0]" in got
        assert "cheat_sheet.rhythm[Every Week][0]" in got
        assert "cheat_sheet.milestones[0]" in got

    def test_edited_text_wins_over_generated_text(self):
        """The control's job is the text a human actually read."""
        got = dict(stored_strings(self._ctx()))
        assert got["section:Profile Signal Clarity"] == "the admin's rewrite"

    def test_unparseable_cheat_sheet_is_surfaced_not_dropped(self):
        ctx = self._ctx()
        ctx["narratives"] = [
            {"section": "cheat_sheet", "generated_text": "{not json"}
        ]
        ctx["scores"] = {"dimensions": {"dimensions": []}}
        got = dict(stored_strings(ctx))
        assert "cheat_sheet:UNPARSEABLE" in got

    def test_the_control_lights_up_on_the_known_bad_text(self):
        """The whole premise of the control: sweeping the delivered b03ca0f5
        text must produce HIGH hits. This is the fixture version of that."""
        ctx = self._ctx()
        ctx["narratives"][0]["generated_text"] = (
            "this activity level is generating meaningful scale"
        )
        hits = sweep(stored_strings(ctx))
        assert [h for h in hits if h["tier"] == "HIGH"]


_CHEAT_SHEET = (
    '{"priorities": [{"title": "Close the Gap", "action": "Do the thing."}], '
    '"rhythm": [{"cadence": "Every Week", "items": ["Post twice."]}], '
    '"milestones": [{"value": "12", "label": "Weeks with at least one post"}]}'
)


class TestTheScriptCannotWrite:
    """The docstring promises this script never writes, and it gets pointed at
    delivered reports on that promise. `regenerate_report.py` sits next to it
    in the same package and does the opposite, so a copy-paste between them is
    a live hazard — this asserts the property at source level rather than
    trusting the claim.

    Reading the source is a blunt check, but the alternative is a mocked
    Supabase client that only proves the paths the test happens to exercise.
    The blunt version catches a write added anywhere in the file.
    """

    def _source(self) -> str:
        from pathlib import Path

        import backend.scripts.claims_sweep as mod

        return Path(mod.__file__).read_text()

    def test_no_supabase_mutation_calls(self):
        import re

        src = self._source()
        # Strip the module docstring, which legitimately discusses writing.
        body = src.split('"""', 2)[-1]
        offenders = re.findall(
            r"^.*\.(?:update|insert|upsert|delete|rpc)\(.*$",
            body,
            re.MULTILINE,
        )
        # `sys.path.insert` is the one permitted `.insert(`.
        offenders = [o for o in offenders if "sys.path.insert" not in o]
        assert offenders == [], (
            "claims_sweep.py must never mutate: " + "; ".join(offenders)
        )

    def test_every_table_access_is_a_select(self):
        """Checked per statement rather than per line — the query builder wraps
        across lines, so a line-based check reports false failures."""
        body = self._source().split('"""', 2)[-1]
        parts = body.split(".table(")[1:]
        assert parts, "expected at least one table access to check"
        for part in parts:
            statement, _, _ = part.partition(".execute(")
            assert ".select(" in statement, (
                "table access without select: .table("
                + statement[:120].replace("\n", " ")
            )


class TestOutcomeTargetsAreInformationalOnly:
    """ORPHEUS-134 explicitly excludes the numeric form of the breach, so the
    sweep must report outcome-target milestones without failing on them —
    otherwise the acceptance run can never go green while the milestone
    decision is open."""

    def test_the_three_outcome_metrics_are_named(self):
        assert set(OUTCOME_TARGET_KEYS) == {
            "impressions_per_post", "followers", "engagement_rate"
        }

    def test_outcome_target_keys_are_not_a_breach_family(self):
        family_ids = {f["id"] for f in FAMILIES}
        assert not any("milestone" in fid.lower() for fid in family_ids)
