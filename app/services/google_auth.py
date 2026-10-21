"""Sign in with Google — the server-side redirect flow, and nothing else.

Why not the usual "Sign in with Google" JavaScript button?
    That button works by loading Google's script (Google Identity Services) into
    our page, which runs inside our origin and can touch its storage. The
    privacy policy promises that *no external scripts load on the page at all*,
    and that promise is worth more to this product than the convenience of the
    button. So instead:

      1. we send the browser to accounts.google.com with an authorization request
      2. the user authenticates there, on Google's own page
      3. Google sends the browser back to our callback with a one-time code
      4. *our server* swaps that code for tokens, over TLS, and reads the identity
         out of the ID token

    No Google script ever executes in our origin and no Google cookie is set on
    our domain.

Two things make the round trip safe:
    - **state**: a random value kept in a signed, httpOnly, short-lived cookie and
      echoed back by Google. A callback whose state does not match the cookie we
      handed out is refused, which is what stops a forged callback from logging
      someone into an attacker's account.
    - **PKCE**: the code exchange presents a `code_verifier` whose hash we sent as
      `code_challenge`, so an intercepted code is useless on its own.

The ID token is not signature-checked, deliberately: it arrives as the direct
response to our own server-to-server POST to Google's token endpoint, over TLS.
Google's own documentation says signature verification may be skipped in exactly
that case — it exists for tokens that reach you through the browser. The claims
that matter (`aud`, `iss`, `exp`, `email_verified`) are still all checked, below.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import time
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

# Read at import, like every other setting here (an env change needs a restart).
# load_dotenv() is called here too rather than relying on some other module
# having imported it first, so the values below do not depend on import order.
load_dotenv()

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

# Google has used both spellings of the issuer over the years.
ISSUERS = {"accounts.google.com", "https://accounts.google.com"}

CLIENT_ID = (os.environ.get("GOOGLE_CLIENT_ID") or "").strip()
CLIENT_SECRET = (os.environ.get("GOOGLE_CLIENT_SECRET") or "").strip()
# Optional. When unset the redirect URI is derived from the incoming request, so
# the flow works on every hostname the app is served from — but each of those
# must then be listed as an Authorized redirect URI in the Google console.
REDIRECT_URI = (os.environ.get("GOOGLE_REDIRECT_URI") or "").strip()

REQUEST_TIMEOUT = 15


class GoogleAuthError(Exception):
    """Something in the Google round trip did not hold up."""


def is_configured() -> bool:
    return bool(CLIENT_ID and CLIENT_SECRET)


def redirect_uri_for(request) -> str:
    """Where Google should send the browser back to.

    Derived from the live request unless the operator pinned one, so the URI
    matches whichever hostname the user actually arrived on.
    """
    if REDIRECT_URI:
        return REDIRECT_URI
    return str(request.base_url).rstrip("/") + "/api/auth/google/callback"


# --------------------------------------------------------------------------- #
# the pieces of the handshake
# --------------------------------------------------------------------------- #
def new_state() -> str:
    return secrets.token_urlsafe(32)


def new_verifier() -> str:
    return secrets.token_urlsafe(64)


def challenge_for(verifier: str) -> str:
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def authorization_url(redirect_uri: str, state: str, code_challenge: str) -> str:
    params = {
        "client_id": CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        # Ask for an account chooser rather than silently reusing whichever
        # Google session happens to be open.
        "prompt": "select_account",
    }
    return AUTH_ENDPOINT + "?" + urlencode(params)


# --------------------------------------------------------------------------- #
# the round trip
# --------------------------------------------------------------------------- #
def _decode_id_token(id_token: str) -> dict:
    """Read the claims out of a JWT without verifying the signature.

    Only ever called on a token that came back from the token endpoint over TLS
    (see the module docstring for why that is enough).
    """
    parts = id_token.split(".")
    if len(parts) != 3:
        raise GoogleAuthError("id token is not a JWT")
    body = parts[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
    except (ValueError, UnicodeDecodeError) as exc:
        raise GoogleAuthError("id token payload is not readable") from exc
    if not isinstance(claims, dict):
        raise GoogleAuthError("id token payload is not an object")
    return claims


def identity_from_id_token(id_token: str) -> dict:
    """Validate the claims and return `{sub, email, name}`.

    Raised as GoogleAuthError for anything Google would not have issued for this
    app: wrong audience, wrong issuer, expired, or an address Google has not
    verified.
    """
    claims = _decode_id_token(id_token)

    if claims.get("aud") != CLIENT_ID:
        raise GoogleAuthError("id token was issued for a different client")
    if claims.get("iss") not in ISSUERS:
        raise GoogleAuthError("id token has an unexpected issuer")
    try:
        if int(claims.get("exp", 0)) < time.time() - 60:
            raise GoogleAuthError("id token has expired")
    except (TypeError, ValueError) as exc:
        raise GoogleAuthError("id token has no usable expiry") from exc

    email = (claims.get("email") or "").strip().lower()
    verified = claims.get("email_verified")
    if isinstance(verified, str):
        verified = verified.strip().lower() == "true"
    if not email or not verified:
        # This is the one that matters: we only ever match or create an account
        # on an address Google itself says belongs to the person signing in.
        raise GoogleAuthError("Google did not report a verified email address")

    sub = claims.get("sub")
    if not sub:
        raise GoogleAuthError("id token has no subject")

    return {"sub": str(sub), "email": email, "name": (claims.get("name") or "").strip()}


def exchange_code(code: str, redirect_uri: str, code_verifier: str) -> dict:
    """Swap an authorization code for tokens, server to server."""
    try:
        response = requests.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise GoogleAuthError(f"could not reach Google: {exc}") from exc

    if response.status_code != 200:
        raise GoogleAuthError(
            f"Google refused the code exchange (HTTP {response.status_code})"
        )
    try:
        return response.json()
    except ValueError as exc:
        raise GoogleAuthError("Google returned a non-JSON token response") from exc


def fetch_identity(code: str, redirect_uri: str, code_verifier: str) -> dict:
    """Everything the callback needs: code -> tokens -> validated identity."""
    tokens = exchange_code(code, redirect_uri, code_verifier)
    id_token = tokens.get("id_token")
    if not id_token:
        raise GoogleAuthError("Google's token response had no id_token")
    return identity_from_id_token(id_token)
