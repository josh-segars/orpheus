"""Transactional-email integration (ORPHEUS-38).

`resend_client` wraps Resend's HTTP API. `templates` (added in commit #3
of ORPHEUS-38) holds the invitation-email subject + body strings.
Endpoints in `backend/routers/clients.py` import from here, never from
the Resend SDK — keeping the wrapper means we can swap providers later
without touching the routers.
"""
