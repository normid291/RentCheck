"""Email one-time codes: issuing, checking, and the resend cooldown.

Rules (from the product spec, enforced here rather than in the router so every
caller gets them):
  - 6 digits, expires in 10 minutes
  - stored hashed, single use
  - at most 5 wrong attempts, then the user must request a new code
  - one code per purpose at a time: issuing a new one retires the old one, so a
    code that leaked from an earlier email cannot still be used
"""
from __future__ import annotations

import math
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models.db import OtpCode, OtpPurpose, User
from app.services.auth import hash_secret, verify_secret

CODE_TTL_MINUTES = 10
CODE_TTL = timedelta(minutes=CODE_TTL_MINUTES)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN_SECONDS = 60

# Return codes from check_code(). The router maps these to human messages, so
# the API never has to guess why verification failed.
OK = ""
NO_CODE = "no_code"
ALREADY_USED = "already_used"
EXPIRED = "expired"
TOO_MANY_ATTEMPTS = "too_many_attempts"
WRONG_CODE = "wrong_code"


def generate_code() -> str:
    """A uniformly random 6-digit code, including leading zeros."""
    return f"{secrets.randbelow(1_000_000):06d}"


def _latest(db: Session, user: User, purpose: OtpPurpose) -> OtpCode | None:
    return (
        db.query(OtpCode)
        .filter(OtpCode.user_id == user.id, OtpCode.purpose == purpose)
        .order_by(OtpCode.created_at.desc())
        .first()
    )


def issue_code(db: Session, user: User, purpose: OtpPurpose) -> str:
    """Create a new code, retiring any outstanding one. Returns the plain code.

    The plain text is returned to the caller only so it can be emailed; it is
    never stored and never logged.
    """
    now = datetime.utcnow()

    (
        db.query(OtpCode)
        .filter(
            OtpCode.user_id == user.id,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
        )
        .update({"consumed_at": now}, synchronize_session=False)
    )

    code = generate_code()
    db.add(
        OtpCode(
            user_id=user.id,
            purpose=purpose,
            code_hash=hash_secret(code),
            expires_at=now + CODE_TTL,
            created_at=now,
            attempts=0,
        )
    )
    db.commit()
    return code


def check_code(
    db: Session, user: User, purpose: OtpPurpose, submitted: str
) -> tuple[bool, str]:
    """Verify a submitted code. Returns (ok, reason). On success it is spent."""
    otp = _latest(db, user, purpose)
    if otp is None:
        return False, NO_CODE
    if otp.consumed_at is not None:
        return False, ALREADY_USED

    now = datetime.utcnow()
    if otp.expires_at <= now:
        return False, EXPIRED
    if otp.attempts >= MAX_ATTEMPTS:
        # Deliberately does not compare: the code is dead either way.
        return False, TOO_MANY_ATTEMPTS

    if verify_secret(otp.code_hash, submitted):
        otp.consumed_at = now
        db.commit()
        return True, OK

    otp.attempts += 1
    db.commit()
    return False, WRONG_CODE


def attempts_remaining(db: Session, user: User, purpose: OtpPurpose) -> int:
    otp = _latest(db, user, purpose)
    if otp is None:
        return MAX_ATTEMPTS
    return max(0, MAX_ATTEMPTS - otp.attempts)


def resend_wait(db: Session, user: User, purpose: OtpPurpose) -> int:
    """Seconds the user must still wait before a new code may be sent (0 = now).

    Keyed off the newest code even if it was already consumed, so spending a
    code does not reset the cooldown.
    """
    otp = _latest(db, user, purpose)
    if otp is None:
        return 0
    elapsed = (datetime.utcnow() - otp.created_at).total_seconds()
    remaining = RESEND_COOLDOWN_SECONDS - elapsed
    if remaining <= 0:
        return 0
    return math.ceil(remaining)
