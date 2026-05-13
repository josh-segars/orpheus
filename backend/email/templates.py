"""Invitation email subject + body content (ORPHEUS-38).

Extracted from backend/email/resend_client.py in commit #3 of
ORPHEUS-38 to separate the visual / copy layer from the HTTP
plumbing. The Resend wrapper imports `format_invitation_email` and
forwards its return value to Resend's REST API.

Why a tuple return shape? Resend's API takes `html` and `text` bodies
as separate fields — text is used by clients that strip HTML (text-
mode email, accessibility readers) and as a fallback when HTML
rendering fails. Returning both from one function pins them to the
same revision in commit history.

Visual design pass deferred (per the spec): v1 ships plain HTML —
no logo, no brand color, no signature, no footer link to ToS /
Privacy. After the first real client receives the email, run a
visual pass and revise this module. The tests are deliberately
snapshot-style on key strings (not full equality) so cosmetic copy
changes don't break the suite.
"""

from __future__ import annotations

INVITATION_EMAIL_SUBJECT = (
    "{advisor_name} invited you to a Strategic Presence Diagnostic"
)


def format_invitation_email(
    *,
    advisor_name: str,
    invite_url: str,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for an invitation email.

    Plain text + plain HTML in v1. The HTML body is intentionally
    minimal so it renders consistently across Gmail / Outlook / Apple
    Mail without per-client tweaks. The text body mirrors the HTML
    line for line so accessibility/text-mode readers get the same
    information.
    """
    subject = INVITATION_EMAIL_SUBJECT.format(advisor_name=advisor_name)

    html_body = (
        f"<p>{advisor_name} invited you to complete a Strategic "
        f"Presence Diagnostic with Orpheus Social.</p>"
        f"<p>To accept the invitation, sign in with LinkedIn:</p>"
        f'<p><a href="{invite_url}">{invite_url}</a></p>'
        f"<p>This link expires in 14 days.</p>"
    )

    text_body = (
        f"{advisor_name} invited you to complete a Strategic "
        f"Presence Diagnostic with Orpheus Social.\n\n"
        f"To accept the invitation, sign in with LinkedIn:\n"
        f"{invite_url}\n\n"
        f"This link expires in 14 days."
    )

    return subject, html_body, text_body
