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
    is_resend: bool = False,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for an invitation email.

    Plain text + plain HTML in v1. The HTML body is intentionally
    minimal so it renders consistently across Gmail / Outlook / Apple
    Mail without per-client tweaks. The text body mirrors the HTML
    line for line so accessibility/text-mode readers get the same
    information.

    `is_resend` (ORPHEUS-93): the resend endpoint rotates the
    invitation token, which kills every previously-emailed link the
    instant the new email goes out. Without saying so, a recipient
    holding the original email clicks the old link, gets the 401
    not-found state, and reads it as "expired." The resend variant
    states explicitly that this email replaces any earlier invitation
    and only the newest link works.
    """
    subject = INVITATION_EMAIL_SUBJECT.format(advisor_name=advisor_name)

    replaces_html = ""
    replaces_text = ""
    if is_resend:
        replaces_html = (
            "<p>This email replaces any invitation we sent you "
            "earlier &mdash; only the link below will work now.</p>"
        )
        replaces_text = (
            "This email replaces any invitation we sent you earlier - "
            "only the link below will work now.\n\n"
        )

    html_body = (
        f"<p>{advisor_name} invited you to complete a Strategic "
        f"Presence Diagnostic with Orpheus Social.</p>"
        f"{replaces_html}"
        f"<p>To accept the invitation, sign in with LinkedIn:</p>"
        f'<p><a href="{invite_url}">{invite_url}</a></p>'
        f"<p>This link expires in 14 days.</p>"
    )

    text_body = (
        f"{advisor_name} invited you to complete a Strategic "
        f"Presence Diagnostic with Orpheus Social.\n\n"
        f"{replaces_text}"
        f"To accept the invitation, sign in with LinkedIn:\n"
        f"{invite_url}\n\n"
        f"This link expires in 14 days."
    )

    return subject, html_body, text_body


REPORT_READY_EMAIL_SUBJECT = "Your Orpheus report is ready — and we'd love your take"


def format_report_ready_email(
    *,
    client_name: str,
    report_url: str,
    survey_url: str | None = None,
) -> tuple[str, str, str]:
    """Return (subject, html_body, text_body) for the report-completion email.

    Sent once per client on first successful report completion (ORPHEUS-81
    means "every successful report" would also fire on re-runs — the
    first-completion guard belongs at the worker call site, not here).

    Voice is second-person direct to match the platform narrative default
    (ORPHEUS-77). Same minimal-HTML posture as the invitation email so it
    renders consistently across Gmail / Outlook / Apple Mail without
    per-client tweaks, and the text body mirrors the HTML line for line.

    `survey_url` is optional and the feedback block renders only when it's
    set — mirrors the frontend's render-only-when-set pattern for
    VITE_BETA_SURVEY_URL, so a non-beta send shows no dead feedback link.
    The worker sources it from a backend env mirror of that form URL.

    No unsubscribe / ToS / Privacy footer in v1 — pending the consent
    review (a feedback solicitation reads closer to marketing than the
    clearly-transactional invitation email). Add the footer here before
    this goes to real beta users.
    """
    subject = REPORT_READY_EMAIL_SUBJECT

    feedback_html = ""
    feedback_text = ""
    if survey_url:
        feedback_html = (
            f"<p>If you have two minutes, we'd be grateful for your "
            f"honest read:</p>"
            f'<p><a href="{survey_url}">Share your feedback &rarr;</a></p>'
        )
        feedback_text = (
            f"If you have two minutes, we'd be grateful for your honest "
            f"read:\n"
            f"{survey_url}\n\n"
        )

    html_body = (
        f"<p>Hi {client_name},</p>"
        f"<p>Your Orpheus report is ready to view.</p>"
        f'<p><a href="{report_url}">View your report &rarr;</a></p>'
        f"<p>You're one of a small group seeing this before anyone else, "
        f"and that's the whole point &mdash; your reaction is what shapes "
        f"where Orpheus goes next. What landed? What felt off? What did "
        f"you wish it told you?</p>"
        f"{feedback_html}"
        f"<p>Thank you for being here early.</p>"
        f"<p>&mdash; The Orpheus Social team</p>"
    )

    text_body = (
        f"Hi {client_name},\n\n"
        f"Your Orpheus report is ready to view.\n"
        f"{report_url}\n\n"
        f"You're one of a small group seeing this before anyone else, "
        f"and that's the whole point - your reaction is what shapes where "
        f"Orpheus goes next. What landed? What felt off? What did you wish "
        f"it told you?\n\n"
        f"{feedback_text}"
        f"Thank you for being here early.\n\n"
        f"- The Orpheus Social team"
    )

    return subject, html_body, text_body
