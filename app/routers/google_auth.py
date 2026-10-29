"""The two endpoints behind "Continue with Google".

The flow, and why it is a redirect rather than Google's JavaScript button, is
explained in app/services/google_auth.py. The short version: no Google script is
ever loaded into our pages.

Two rules carry over from app/routers/auth.py and are the reason the code below
is fussier than it looks:

  - a real failure tells the user something useful and specific, but never
    anything they did not already know; a cancellation is not a failure at all
    and returns silently
  - the account a Google identity lands on is decided by Google's verified
    `sub` first and the verified email second, never by an address the caller
    merely claimed

Both buttons — Log in and Sign up — call the same `/auth/google/start`, so the
two pages cannot drift apart: a brand-new Google account signs up and signs in
in one step from either.
"""
from __future__ import annotations

import logging
import secrets
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.routers.auth import guard
from app.services import google_auth
from app.services.redirects import safe_next_path
from app.services.auth import (
    OAUTH_STATE_COOKIE,
    GoogleAccountConflict,
    clear_oauth_state_cookie,
    read_oauth_state_cookie,
    resolve_google_user,
    set_oauth_state_cookie,
    set_session_cookie,
)
from app.services.ratelimit import client_ip, limiter

router = APIRouter()

logger = logging.getLogger("tenura.google")

# Generous: this only guards against the endpoint being hammered, and a real
# person may retry a couple of times if they pick the wrong Google account.
GOOGLE_IP = (30, 600)

# The only pages that host a "Continue with Google" button. The callback returns
# the visitor to whichever one they started from, so a failure on the sign-up
# page does not silently bounce them to the log-in page (and vice versa).
_ORIGINS = ("/login", "/signup")
_DEFAULT_ORIGIN = "/login"

_NOT_CONFIGURED = "Google sign-in is not configured on this server."


def _safe_next(value: str | None) -> str:
    """Only same-site paths, the same rule the browser applies to `?next=`."""
    return safe_next_path(value, "/")


def _safe_origin(value: str | None) -> str:
    """The page to come back to: /login or /signup, never anything else."""
    origin = safe_next_path(value, _DEFAULT_ORIGIN)
    return origin if origin in _ORIGINS else _DEFAULT_ORIGIN


def _return(origin: str, error: str | None = None, next_path: str = "/") -> RedirectResponse:
    """Send the visitor back to the page they started from.

    `error` is a short, specific code the page maps to a friendly message
    (app/static/common.js). It is None for a quiet return - used when the person
    simply cancelled Google's screen, which is not a failure worth a banner.
    """
    params: dict[str, str] = {}
    if error:
        params["error"] = error
    if next_path and next_path != "/":
        params["next"] = next_path
    url = origin + ("?" + urlencode(params) if params else "")
    response = RedirectResponse(url, status_code=status.HTTP_303_SEE_OTHER)
    clear_oauth_state_cookie(response)
    return response


@router.get("/auth/google/start", include_in_schema=False)
def google_start(request: Request):
    """Send the browser to Google to choose an account and consent."""
    if not google_auth.is_configured():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_CONFIGURED
        )
    guard(request, (f"google:ip:{client_ip(request)}", GOOGLE_IP))

    redirect_uri = google_auth.redirect_uri_for(request)
    state = google_auth.new_state()
    verifier = google_auth.new_verifier()
    target = _safe_next(request.query_params.get("next"))
    origin = _safe_origin(request.query_params.get("from"))

    response = RedirectResponse(
        google_auth.authorization_url(
            redirect_uri, state, google_auth.challenge_for(verifier)
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    set_oauth_state_cookie(
        response,
        {"state": state, "verifier": verifier, "next": target, "origin": origin},
    )
    return response


@router.get("/auth/google/callback", include_in_schema=False)
def google_callback(
    request: Request,
    code: str = "",
    state: str = "",
    error: str = "",
    db: Session = Depends(get_db),
):
    """Come back from Google: verify, match or create the account, sign in."""
    if not google_auth.is_configured():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=_NOT_CONFIGURED
        )
    guard(request, (f"google:ip:{client_ip(request)}", GOOGLE_IP))

    pending = read_oauth_state_cookie(request.cookies.get(OAUTH_STATE_COOKIE))
    origin = _safe_origin(pending.get("origin")) if pending else _DEFAULT_ORIGIN
    target = _safe_next(pending.get("next")) if pending else "/"

    if error:
        # The user dismissed Google's screen (access_denied), or Google itself
        # declined. A cancellation is not a failure: return them to the button
        # they pressed with no error at all. Any other Google-side error is a
        # real one and gets the generic "try again".
        return _return(origin, None if error == "access_denied" else "google", target)

    # The state we handed out must come back unchanged, or this is not our
    # callback. Also covers a code-less callback.
    if (
        not code
        or not pending
        or not state
        or not secrets.compare_digest(state, str(pending.get("state") or ""))
    ):
        return _return(origin, "google", target)

    try:
        identity = google_auth.fetch_identity(
            code,
            google_auth.redirect_uri_for(request),
            str(pending.get("verifier") or ""),
        )
    except google_auth.GoogleUnavailableError:
        # We could not reach Google at all - worth a connection-flavoured retry.
        logger.warning("google sign-in unavailable: could not reach Google")
        return _return(origin, "google_unavailable", target)
    except google_auth.GoogleAuthError as exc:
        # Never log the code or the tokens — just the reason.
        logger.warning("google sign-in refused: %s", type(exc).__name__)
        return _return(origin, "google", target)

    try:
        user, _created = resolve_google_user(db, identity["email"], identity["sub"])
    except GoogleAccountConflict:
        # This verified address is already bound to a different Google account.
        logger.warning("google sign-in refused: address linked to another Google account")
        return _return(origin, "google_conflict", target)

    limiter.reset(f"login:email:{user.email}")

    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    clear_oauth_state_cookie(response)
    set_session_cookie(response, user)
    return response
