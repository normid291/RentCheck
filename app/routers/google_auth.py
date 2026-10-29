"""The two endpoints behind "Continue with Google".

The flow, and why it is a redirect rather than Google's JavaScript button, is
explained in app/services/google_auth.py. The short version: no Google script is
ever loaded into our pages.

Two rules carry over from app/routers/auth.py and are the reason the code below
is fussier than it looks:

  - a failure tells the user nothing they did not already know, so every way the
    callback can go wrong lands on the same "please try again" message
  - the account a Google identity lands on is decided by Google's verified
    `sub` first and the verified email second, never by an address the caller
    merely claimed
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
    clear_oauth_state_cookie,
    create_user_with_google,
    get_user_by_email,
    get_user_by_google_sub,
    link_google_account,
    read_oauth_state_cookie,
    set_oauth_state_cookie,
    set_session_cookie,
)
from app.services.ratelimit import client_ip, limiter

router = APIRouter()

logger = logging.getLogger("tenura.google")

# Generous: this only guards against the endpoint being hammered, and a real
# person may retry a couple of times if they pick the wrong Google account.
GOOGLE_IP = (30, 600)

_NOT_CONFIGURED = "Google sign-in is not configured on this server."


def _safe_next(value: str | None) -> str:
    """Only same-site paths, the same rule the browser applies to `?next=`."""
    return safe_next_path(value, "/")


def _failure(next_path: str) -> RedirectResponse:
    """One response for every way the callback can fail."""
    params = {"error": "google"}
    if next_path and next_path != "/":
        params["next"] = next_path
    response = RedirectResponse(
        "/login?" + urlencode(params), status_code=status.HTTP_303_SEE_OTHER
    )
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

    response = RedirectResponse(
        google_auth.authorization_url(
            redirect_uri, state, google_auth.challenge_for(verifier)
        ),
        status_code=status.HTTP_303_SEE_OTHER,
    )
    set_oauth_state_cookie(
        response, {"state": state, "verifier": verifier, "next": target}
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
    target = _safe_next(pending.get("next")) if pending else "/"

    # The state we handed out must come back unchanged, or this is not our
    # callback. Also covers the user pressing "deny" on Google's screen (which
    # arrives as ?error=access_denied, with no code at all).
    if (
        error
        or not code
        or not pending
        or not state
        or not secrets.compare_digest(state, str(pending.get("state") or ""))
    ):
        return _failure(target)

    try:
        identity = google_auth.fetch_identity(
            code,
            google_auth.redirect_uri_for(request),
            str(pending.get("verifier") or ""),
        )
    except google_auth.GoogleAuthError as exc:
        # Never log the code or the tokens — just the reason.
        logger.warning("google sign-in refused: %s", type(exc).__name__)
        return _failure(target)

    user = get_user_by_google_sub(db, identity["sub"])

    if user is None:
        existing = get_user_by_email(db, identity["email"])
        if existing is not None:
            if existing.google_sub and existing.google_sub != identity["sub"]:
                # This address already belongs to a different Google account.
                logger.warning("google sign-in refused: address linked to another Google account")
                return _failure(target)
            # Same address, either already ours or an email/password account the
            # user is now choosing to sign into with Google. Link them: Google
            # has verified the address, so this is the user proving it is theirs.
            link_google_account(db, existing, identity["sub"])
            user = existing
        else:
            user = create_user_with_google(db, identity["email"], identity["sub"])

    limiter.reset(f"login:email:{user.email}")

    response = RedirectResponse(target, status_code=status.HTTP_303_SEE_OTHER)
    clear_oauth_state_cookie(response)
    set_session_cookie(response, user)
    return response
