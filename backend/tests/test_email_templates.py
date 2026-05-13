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
    format_invitation_email,
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
