"""Outbound email: the OTP messages, and nothing else.

Provider: Resend (https://resend.com) — a plain REST call, which matches how the
rest of this app talks to Rumpty AI Inference. Swap `PROVIDER` for another
provider and only `_send_resend` needs rewriting.

Configuration
    EMAIL_PROVIDER   "resend" | "console"  (optional; inferred from the key)
    RESEND_API_KEY   required for the resend provider
    EMAIL_FROM       e.g. "RentCheck <no-reply@example.com>" (must be a domain
                     you have verified with the provider)
    APP_ENV          "production" refuses the console provider outright

No OTP is ever written to a log. The console provider is the one exception, and
it exists only so the flows can be exercised locally without a provider account:
it must be asked for by name (`EMAIL_PROVIDER=console`), and it refuses to run
when APP_ENV says production. Nothing is sent, and nothing is logged, by
accident.
"""
from __future__ import annotations

import os

import requests
from dotenv import load_dotenv

# Read the project's .env before the environment lookups below. This module has
# no other reason to import app.database (which is what normally loads it), and
# the values below are captured at import time - so without this line the
# provider settings would only be seen if something else happened to import the
# database first. ai_inference.py does the same thing, for the same reason.
load_dotenv()

RESEND_ENDPOINT = "https://api.resend.com/emails"
REQUEST_TIMEOUT = 20

PROVIDER_ENV = (os.environ.get("EMAIL_PROVIDER") or "").strip().lower()
RESEND_API_KEY = (os.environ.get("RESEND_API_KEY") or "").strip()
EMAIL_FROM = (os.environ.get("EMAIL_FROM") or "").strip()
APP_ENV = (os.environ.get("APP_ENV") or "development").strip().lower()

IS_PRODUCTION = APP_ENV in ("production", "prod")

_SUBJECTS = {
    "verify_email": "Your RentCheck verification code",
    "reset_password": "Your RentCheck password reset code",
}


class EmailError(Exception):
    """Raised when a message could not be handed to the provider."""


def provider_name() -> str:
    """Which provider will actually be used, given the environment."""
    if PROVIDER_ENV:
        return PROVIDER_ENV
    if RESEND_API_KEY:
        return "resend"
    return "unconfigured"


def otp_message(code: str, purpose: str, minutes: int) -> tuple[str, str]:
    """Return (subject, plain-text body) for an OTP email.

    Deliberately plain: no tracking pixels, no remote images, no links that leak
    the code, and the code is repeated in the subject-free body so it is easy to
    read on a phone.
    """
    subject = _SUBJECTS.get(purpose, "Your RentCheck code")

    if purpose == "reset_password":
        opening = "Use this code to reset your RentCheck password:"
        closing = (
            "If you did not ask to reset your password, you can ignore this "
            "email — your password will not change."
        )
    else:
        opening = "Use this code to verify your email and activate your RentCheck account:"
        closing = "If you did not create a RentCheck account, you can ignore this email."

    body = (
        f"{opening}\n\n"
        f"    {code}\n\n"
        f"The code expires in {minutes} minutes and can only be used once. "
        f"You have 5 attempts before you need to request a new one.\n\n"
        f"{closing}\n\n"
        f"— RentCheck\n"
    )
    return subject, body


def send_email(to: str, subject: str, body: str) -> None:
    """Send one plain-text email. Raises EmailError on failure."""
    provider = provider_name()

    if provider == "console":
        if IS_PRODUCTION:
            raise EmailError(
                "EMAIL_PROVIDER=console is refused when APP_ENV=production. "
                "Set RESEND_API_KEY and EMAIL_FROM instead."
            )
        # Development only, and only when explicitly asked for. Loud on purpose
        # so it is never mistaken for a real send.
        print("=" * 68)
        print("[email] DEV CONSOLE PROVIDER — no email was actually sent")
        print(f"[email] to:      {to}")
        print(f"[email] subject: {subject}")
        for line in body.splitlines():
            if line.strip():
                print(f"[email]   {line}")
        print("=" * 68)
        return

    if provider == "resend":
        _send_resend(to, subject, body)
        return

    if provider == "unconfigured":
        raise EmailError(
            "Email is not configured, so this code could not be sent. Set "
            "RESEND_API_KEY and EMAIL_FROM (see .env.example). For local "
            "development you can set EMAIL_PROVIDER=console instead, which "
            "prints the code to the server console and sends nothing."
        )

    raise EmailError(f"Unknown EMAIL_PROVIDER {provider!r}.")


def _send_resend(to: str, subject: str, body: str) -> None:
    if not RESEND_API_KEY:
        raise EmailError("RESEND_API_KEY is not set.")
    if not EMAIL_FROM:
        raise EmailError(
            "EMAIL_FROM is not set. It must be an address on a domain you have "
            "verified with Resend, e.g. 'RentCheck <no-reply@yourdomain.com>'."
        )

    try:
        response = requests.post(
            RESEND_ENDPOINT,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": EMAIL_FROM,
                "to": [to],
                "subject": subject,
                "text": body,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.exceptions.RequestException as exc:
        raise EmailError(f"Could not reach the email provider: {exc}") from exc

    if response.status_code >= 400:
        # Do NOT echo the provider's body: it may quote the request back, and the
        # request contains the code. The provider's error name is safe and is
        # enough to diagnose (e.g. an unverified sending domain).
        name = ""
        try:
            name = (response.json() or {}).get("name") or ""
        except ValueError:
            name = ""
        suffix = f" ({name})" if name else ""
        raise EmailError(
            f"Email provider returned {response.status_code}{suffix}."
        )
