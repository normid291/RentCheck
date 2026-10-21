"""Accounts: password hashing, signed session cookies, and auth dependencies.

Sessions are a signed, expiring cookie rather than a token in localStorage:
  - the value is `user_id.expires.HMAC-SHA256(...)` — stdlib only, no extra table
  - the cookie is httpOnly (JavaScript cannot read it, so XSS cannot exfiltrate
    it), Secure, and SameSite=Lax (so a cross-site form post does not carry it)
  - nothing is ever returned in a JSON body for the client to store

`SESSION_SECRET` signs every cookie. If it is not set we generate a random key
for the process, which means every restart silently signs everyone out — so it
is set in production and we say so loudly when it is missing.
"""
from __future__ import annotations

import hashlib
import hmac
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


def verify_password(stored_hash: str, password: str) -> bool:
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


def set_password(db: Session, user: User, password: str) -> None:
    user.password_hash = hash_password(password)
    db.commit()


def mark_verified(db: Session, user: User) -> None:
    if not user.is_verified:
        user.is_verified = True
    user.verified_at = datetime.utcnow()
    db.commit()


# --------------------------------------------------------------------------- #
# session tokens
# --------------------------------------------------------------------------- #
def make_session_token(user_id, ttl_seconds: int = SESSION_TTL_SECONDS) -> str:
    expires = int(time.time()) + ttl_seconds
    payload = f"{user_id}.{expires}"
    signature = hmac.new(SESSION_SECRET, payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def read_session_token(token: str) -> str | None:
    """Return the user id from a valid, unexpired token, else None."""
    if not token:
        return None
    parts = token.split(".")
    if len(parts) != 3:
        return None
    user_id, expires, signature = parts
    expected = hmac.new(
        SESSION_SECRET, f"{user_id}.{expires}".encode(), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    try:
        if int(expires) < time.time():
            return None
    except ValueError:
        return None
    return user_id


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
