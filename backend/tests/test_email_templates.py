"""Unit tests for backend/email/templates.py.

Snapshot-style assertions on key strings, not full equality. The v1
copy ships with plain HTML; a visual design pass will revise it after
the first client sees the email. These tests pin the structural
invariants (advisor name in subject, URL in both bodies, HTML wraps
the URL as a clickable link) so cosmetic edits don't break the suite
but a regression on the wire-up contract does.
"""

from __future__ import annotations

from backend.email.templates import (
    INVITATION_EMAIL_SUBJECT,
    REPORT_READY_EMAIL_SUBJECT,
    format_invitation_email,
    format_report_ready_email,
)


def test_subject_template_includes_advisor_name():
    """Subject template must interpolate the advisor's name and name the deliverable."""
    subject = INVITATION_EMAIL_SUBJECT.format(advisor_name="Andrew Segars")

    assert "Andrew Segars" in subject
    assert "Strategic Presence Diagnostic" in subject


def test_format_invitation_email_returns_three_non_empty_strings():
    """Contract: returns (subject, html, text). All three strings, all non-empty.

    Mirrors the Resend API's required fields (`subject`, `html`, `text`).
    Empty values would slip past the type system but be silently rejected
    by Resend at send time — easier to catch here.
    """
    subject, html, text = format_invitation_email(
        advisor_name="Andrew Segars",
        invite_url="https://app.orpheussocial.com/invite/abc123",
    )

    assert isinstance(subject, str) and subject
    assert isinstance(html, str) and html
    assert isinstance(text, str) and text
    assert "Andrew Segars" in subject


def test_format_invitation_email_embeds_invite_url_in_both_bodies():
    """The invite URL must appear in HTML (as href) and text (raw)."""
    url = "https://app.orpheussocial.com/invite/abc123"
    _, html, text = format_invitation_email(
        advisor_name="Andrew Segars",
        invite_url=url,
    )

    assert url in html
    assert url in text
    # And the HTML must wrap it as a link, not just display the URL —
    # otherwise email clients won't make it clickable.
    assert f'href="{url}"' in html


# --------------------------------------------------------------------------- #
# Resend variant (ORPHEUS-93)
# --------------------------------------------------------------------------- #


def test_format_invitation_email_resend_variant_states_replacement():
    """is_resend=True adds the replaces-the-earlier-link line to both bodies.

    Resend rotates the token, killing the previously-emailed link — the
    resend copy must say so or recipients holding the old email read the
    401 as 'expired' (the ORPHEUS-93 live-beta finding).
    """
    url = "https://app.orpheussocial.com/invite/abc123"
    _, html, text = format_invitation_email(
        advisor_name="Andrew Segars",
        invite_url=url,
        is_resend=True,
    )

    assert "replaces any invitation" in html
    assert "replaces any invitation" in text
    # The rest of the invitation copy still renders.
    assert f'href="{url}"' in html
    assert url in text


def test_format_invitation_email_default_omits_replacement_line():
    """First-send copy (default) must not mention replacing an earlier link."""
    _, html, text = format_invitation_email(
        advisor_name="Andrew Segars",
        invite_url="https://app.orpheussocial.com/invite/abc123",
    )

    assert "replaces" not in html.lower()
    assert "replaces" not in text.lower()


# --------------------------------------------------------------------------- #
# Report-ready email (ORPHEUS-98)
# --------------------------------------------------------------------------- #

REPORT_URL = "https://app.orpheussocial.com/reports"
SURVEY_URL = "https://forms.gle/exampleBetaForm"


def test_format_report_ready_email_returns_three_non_empty_strings():
    """Contract: returns (subject, html, text). All three non-empty strings."""
    subject, html, text = format_report_ready_email(
        client_name="Jordan Rivera",
        report_url=REPORT_URL,
    )

    assert isinstance(subject, str) and subject
    assert isinstance(html, str) and html
    assert isinstance(text, str) and text
    assert subject == REPORT_READY_EMAIL_SUBJECT


def test_format_report_ready_email_greets_client_and_links_report():
    """Client name greets the body; report URL appears in both bodies, href in HTML."""
    _, html, text = format_report_ready_email(
        client_name="Jordan Rivera",
        report_url=REPORT_URL,
    )

    assert "Jordan Rivera" in html
    assert "Jordan Rivera" in text
    assert REPORT_URL in html
    assert REPORT_URL in text
    assert f'href="{REPORT_URL}"' in html


def test_format_report_ready_email_includes_feedback_cta_when_survey_set():
    """When survey_url is set, the feedback CTA renders in both bodies."""
    _, html, text = format_report_ready_email(
        client_name="Jordan Rivera",
        report_url=REPORT_URL,
        survey_url=SURVEY_URL,
    )

    assert SURVEY_URL in html
    assert f'href="{SURVEY_URL}"' in html
    assert SURVEY_URL in text


def test_format_report_ready_email_omits_feedback_cta_when_survey_unset():
    """When survey_url is None, no feedback block / no dead link is rendered.

    Mirrors the frontend's render-only-when-set pattern for the survey
    button — an unconfigured BETA_SURVEY_URL must ship a clean thank-you,
    never an empty or broken CTA.
    """
    _, html, text = format_report_ready_email(
        client_name="Jordan Rivera",
        report_url=REPORT_URL,
        survey_url=None,
    )

    # The thank-you still renders...
    assert "Jordan Rivera" in html
    assert REPORT_URL in html
    # ...but nothing feedback-related leaks in.
    assert "feedback" not in html.lower()
    assert "feedback" not in text.lower()
