"""Accounts: password hashing, signed session cookies, and auth dependencies.

Sessions are a signed, expiring cookie rather than a token in localStorage:
  - the value is `base64url(payload).expires.HMAC-SHA256(...)` — stdlib only, no
    extra table, and the same signing serves the short-lived OAuth handoff
    cookie (see the OAuth section below)
  - the cookie is httpOnly (JavaScript cannot read it, so XSS cannot exfiltrate
    it), Secure, and SameSite=Lax (so a cross-site form post does not carry it)
  - nothing is ever returned in a JSON body for the client to store

`SESSION_SECRET` signs every cookie. If it is not set we generate a random key
for the process, which means every restart silently signs everyone out — so it
is set in production and we say so loudly when it is missing.
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import uuid
from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import Depends, HTTPException, Request, Response, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import User

# --------------------------------------------------------------------------- #
# configuration
# --------------------------------------------------------------------------- #
SESSION_COOKIE = "tenura_session"
SESSION_TTL_SECONDS = 30 * 24 * 3600  # 30 days

MIN_PASSWORD_LENGTH = 8
MAX_PASSWORD_LENGTH = 128  # argon2 has no practical limit; this just stops abuse
MAX_EMAIL_LENGTH = 320

SECRET_ENV = (os.environ.get("SESSION_SECRET") or "").strip()
if SECRET_ENV:
    SESSION_SECRET = SECRET_ENV.encode()
else:
    SESSION_SECRET = secrets.token_urlsafe(48).encode()
    print(
        "[auth] WARNING: SESSION_SECRET is not set - using a random key for this "
        "process. Everyone will be signed out on every restart. Set SESSION_SECRET "
        "to a long random value in production."
    )

# Secure cookies are only sent over HTTPS. Local development over plain http
# therefore needs SESSION_COOKIE_SECURE=false, which .env.example shows.
COOKIE_SECURE = (os.environ.get("SESSION_COOKIE_SECURE") or "true").strip().lower() not in (
    "0",
    "false",
    "no",
)

_ph = PasswordHasher()

# Deliberately permissive. Over-strict email regexes reject valid addresses, and
# the only address that really matters is one the user can receive mail at — the
# OTP is the actual proof.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(?:\.[^@\s.]+)+$")


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #
def normalise_email(email: str) -> str:
    """Lowercase and trim, so accounts cannot differ only by case."""
    return (email or "").strip().lower()


def validate_email(email: str) -> str | None:
    """Return an error message, or None if the address looks usable."""
    if not email:
        return "Please enter your email address."
    if len(email) > MAX_EMAIL_LENGTH:
        return "That email address is too long."
    if not _EMAIL_RE.match(email):
        return "Please enter a valid email address."
    return None


def validate_password(password: str, email: str = "") -> str | None:
    """Return an error message, or None if the password is acceptable."""
    if not password:
        return "Please choose a password."
    if len(password) < MIN_PASSWORD_LENGTH:
        return f"Your password must be at least {MIN_PASSWORD_LENGTH} characters."
    if len(password) > MAX_PASSWORD_LENGTH:
        return f"Your password must be at most {MAX_PASSWORD_LENGTH} characters."
    if password.strip() == "":
        return "Your password cannot be only spaces."
    if email and password.lower() == email.lower():
        return "Your password cannot be the same as your email address."
    return None


# --------------------------------------------------------------------------- #
# passwords
# --------------------------------------------------------------------------- #
def hash_password(password: str) -> str:
    return _ph.hash(password)


def hash_secret(value: str) -> str:
    """Hash a short secret such as an OTP code.

    Same hasher as passwords: a 6-digit code is only 10^6 wide, so a fast hash
    would be brute-forced instantly if the table ever leaked.
    """
    return _ph.hash(value)


def verify_password(stored_hash: str | None, password: str) -> bool:
    if not stored_hash:
        # An account created through Google sign-in has no password at all, so
        # there is nothing to compare against: every password is wrong. (Without
        # this guard the hasher would raise on None, which is why it is here and
        # not merely tidy.)
        return False
    try:
        _ph.verify(stored_hash, password)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def verify_secret(stored_hash: str, value: str) -> bool:
    return verify_password(stored_hash, value)


def needs_rehash(stored_hash: str) -> bool:
    """True when the stored hash used weaker parameters than we now use."""
    try:
        return _ph.check_needs_rehash(stored_hash)
    except InvalidHashError:
        return False


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
def get_user_by_email(db: Session, email: str) -> User | None:
    normalised = normalise_email(email)
    if not normalised:
        return None
    return db.query(User).filter(func.lower(User.email) == normalised).one_or_none()


def get_user_by_id(db: Session, user_id) -> User | None:
    try:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    except (ValueError, TypeError, AttributeError):
        return None
    return db.get(User, uid)


def create_user(db: Session, email: str, password: str) -> User:
    user = User(
        email=normalise_email(email),
        password_hash=hash_password(password),
        is_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def get_user_by_google_sub(db: Session, sub: str) -> User | None:
    """The account bound to a Google account id, if any."""
    if not sub:
        return None
    return db.query(User).filter(User.google_sub == sub).one_or_none()


def create_user_with_google(db: Session, email: str, sub: str) -> User:
    """An account created by signing in with Google.

    It has no password — Google is the only way in until the user sets one
    through "forgot password". Google has already proved the address belongs to
    them, so the account starts verified; making them run the email code
    afterwards would prove the same thing twice.
    """
    user = User(
        email=normalise_email(email),
        password_hash=None,
        is_verified=True,
        google_sub=sub,
        verified_at=datetime.utcnow(),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def link_google_account(db: Session, user: User, sub: str) -> None:
    """Attach a Google identity to an existing account, and verify it.

    Only reached once Google has told us the address is verified, so marking the
    account verified is justified — it is the same proof the emailed code gives.
    """
    user.google_sub = sub
    if not user.is_verified:
        user.is_verified = True
    user.verified_at = datetime.utcnow()
    db.commit()


class GoogleAccountConflict(Exception):
    """The verified address already belongs to a different Google account.

    The one Google outcome we refuse rather than resolve: linking would hand one
    person's history (and session) to whoever controls the other Google account.
    """


def resolve_google_user(db: Session, email: str, sub: str) -> tuple[User, bool]:
    """Find the account a Google identity belongs to, creating it if new.

    This is the single "find or create" the whole Google flow runs through, so
    the Log in and Sign up buttons can never diverge. The account is decided by
    Google's stable `sub` first and the verified email second:

      - a returning Google user is matched by `sub` and logged in
      - a brand-new identity gets an account with no password
      - an identity whose email already has a password account is LINKED to it
        (Google has verified the address, so this is the owner proving it is
        theirs), leaving the password working

    Returns `(user, created)` where `created` is True only for a brand-new
    account. Raises `GoogleAccountConflict` when the address is already bound to
    a different Google account.

    Safe under a double-click or two simultaneous callbacks: the unique email
    index rejects the losing insert, and we fall back to reading the row the
    winner wrote instead of surfacing a 500.
    """
    user = get_user_by_google_sub(db, sub)
    if user is not None:
        return user, False

    existing = get_user_by_email(db, email)
    if existing is not None:
        if existing.google_sub and existing.google_sub != sub:
            raise GoogleAccountConflict()
        link_google_account(db, existing, sub)
        return existing, False

    try:
        return create_user_with_google(db, email, sub), True
    except IntegrityError:
        # Lost a race with a concurrent callback for the same identity: the row
        # now exists, so read it rather than failing the sign-in.
        db.rollback()
        user = get_user_by_google_sub(db, sub) or get_user_by_email(db, email)
        if user is None:
            raise
        if user.google_sub and user.google_sub != sub:
            raise GoogleAccountConflict() from None
        if not user.google_sub:
            link_google_account(db, user, sub)
        return user, False


def set_password(db: Session, user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    db.commit()


def mark_verified(db: Session, user: User) -> None:
    if not user.is_verified:
        user.is_verified = True
    user.verified_at = datetime.utcnow()
    db.commit()


# --------------------------------------------------------------------------- #
# signed, expiring values
# --------------------------------------------------------------------------- #
def sign_token(payload: bytes, ttl_seconds: int) -> str:
    """Base64url the payload and sign it together with an expiry.

    One implementation, shared by the session cookie and the short-lived cookie
    that carries OAuth state across the redirect to Google, so there is exactly
    one place where the signing and the constant-time comparison have to be
    right. The token is `payload.expires.HMAC-SHA256(payload.expires)`.
    """
    body = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    expires = int(time.time()) + ttl_seconds
    message = f"{body}.{expires}"
    signature = hmac.new(SESSION_SECRET, message.encode(), hashlib.sha256).hexdigest()
    return f"{message}.{signature}"


def read_token(token: str) -> bytes | None:
    """The payload of a valid, unexpired, untampered token, else None."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    body, expires, signature = parts
    expected = hmac.new(
        SESSION_SECRET, f"{body}.{expires}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        if int(expires) < time.time():
            return None
    except ValueError:
        return None
    try:
        return base64.urlsafe_b64decode(body + "=" * (-len(body) % 4))
    except (ValueError, binascii.Error):
        return None


# --------------------------------------------------------------------------- #
# session tokens
# --------------------------------------------------------------------------- #
def make_session_token(user_id, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    return sign_token(str(user_id).encode("ascii"), ttl_seconds)


def read_session_token(token: str) -> str | None:
    """Return the user id from a valid, unexpired token, else None."""
    payload = read_token(token or "")
    if payload is None:
        return None
    try:
        return payload.decode("ascii")
    except UnicodeDecodeError:
        return None


def set_session_cookie(response: Response, user: User) -> None:
    response.set_cookie(
        key=SESSION_COOKIE,
        value=make_session_token(user.id),
        max_age=SESSION_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


# --------------------------------------------------------------------------- #
# OAuth handoff cookie
# --------------------------------------------------------------------------- #
# Carries the `state` and PKCE `verifier` between the redirect to Google and the
# callback that comes back. Signed with the same secret as the session, lives
# only minutes, and is httpOnly so no page script can read it.
#
# SameSite=Lax, deliberately not Strict: the callback is a top-level GET
# navigation arriving from accounts.google.com, and a Strict cookie is not sent
# on a cross-site navigation, so the callback would never find its own state.
OAUTH_STATE_COOKIE = "tenura_oauth"
OAUTH_STATE_TTL_SECONDS = 10 * 60


def set_oauth_state_cookie(response: Response, value: dict) -> None:
    payload = json.dumps(value, separators=(",", ":")).encode("utf-8")
    response.set_cookie(
        key=OAUTH_STATE_COOKIE,
        value=sign_token(payload, OAUTH_STATE_TTL_SECONDS),
        max_age=OAUTH_STATE_TTL_SECONDS,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


def read_oauth_state_cookie(token: str | None) -> dict | None:
    payload = read_token(token or "")
    if payload is None:
        return None
    try:
        value = json.loads(payload.decode("utf-8"))
    except (ValueError, UnicodeDecodeError):
        return None
    return value if isinstance(value, dict) else None


def clear_oauth_state_cookie(response: Response) -> None:
    response.delete_cookie(
        key=OAUTH_STATE_COOKIE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
        path="/",
    )


# --------------------------------------------------------------------------- #
# dependencies
# --------------------------------------------------------------------------- #
def get_current_user(
    request: Request, db: Session = Depends(get_db)
) -> User | None:
    """The signed-in user, or None. Never raises — use for optional auth."""
    token = request.cookies.get(SESSION_COOKIE)
    user_id = read_session_token(token or "")
    if not user_id:
        return None
    return get_user_by_id(db, user_id)


def require_user(user: User | None = Depends(get_current_user)) -> User:
    """The signed-in user, or 401. Use for anything that needs an owner."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Please sign in to continue.",
        )
    return user
