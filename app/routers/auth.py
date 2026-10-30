"""Accounts: sign up, verify, log in, log out, reset.

Two privacy rules shape this file:

1. Nothing here reveals whether an email address has an account, unless the
   caller has already proved they own it (i.e. they supplied the correct
   password). So:
     - sign-up always answers the same way, whatever happened behind it
     - a failed login is one message for both "no such email" and "wrong
       password", and the unknown-email path still pays the cost of a password
       hash so the response time does not give it away either
     - every one-time-code failure is one message, for the same reason
2. No code, and no agreement text, is ever logged. Codes are only ever handed to
   app/services/email.py to be mailed.

Rate limits are applied per client address AND per email address. The per-email
budget is the one that cannot be spoofed.
"""
from __future__ import annotations

import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import OtpPurpose, User
from app.services import email as email_service
from app.services import google_auth
from app.services import otp
from app.services.admin_access import is_admin
from app.services.auth import (
    clear_session_cookie,
    create_user,
    get_current_user,
    get_user_by_email,
    hash_password,
    mark_verified,
    needs_rehash,
    normalise_email,
    set_password,
    set_session_cookie,
    validate_email,
    validate_password,
    verify_password,
)
from app.services.ratelimit import client_ip, limiter

router = APIRouter()

logger = logging.getLogger("tenura.auth")

# (limit, window_seconds) per policy.
SIGNUP_IP = (10, 3600)
SIGNUP_EMAIL = (3, 3600)
RESEND_IP = (20, 3600)
LOGIN_IP = (20, 300)
LOGIN_EMAIL = (6, 300)
OTP_IP = (30, 600)
OTP_EMAIL = (12, 600)
FORGOT_IP = (10, 3600)
FORGOT_EMAIL = (3, 3600)

# One message for every code failure. Splitting them ("expired" vs "not
# correct") would tell anyone who submits a junk code whether an address has an
# account, which is exactly what rule 1 above forbids.
_OTP_FAILURE = "That code is not correct or has expired. Request a new code and try again."

# Verified against when the email is unknown, purely to spend the same time an
# argon2 check on a real account would take.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(24))


class SignupIn(BaseModel):
    email: str
    password: str = Field(min_length=1)


class EmailIn(BaseModel):
    email: str


class VerifyOtpIn(BaseModel):
    email: str
    code: str = Field(min_length=1, max_length=12)


class LoginIn(BaseModel):
    email: str
    password: str = Field(min_length=1)


class ResendOtpIn(BaseModel):
    email: str
    purpose: str = "verify_email"


class ResetPasswordIn(BaseModel):
    email: str
    code: str = Field(min_length=1, max_length=12)
    password: str = Field(min_length=1)


def user_payload(user: User) -> dict:
    """The only shape a user is ever serialised in. Never includes the hash."""
    return {
        "id": str(user.id),
        "email": user.email,
        "is_verified": bool(user.is_verified),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        # Read-only flags describing how the account signs in, so the Profile
        # page can show the right sections (and hide the password section for a
        # Google-only account). Neither reveals anything beyond what the signed-in
        # owner already knows about their own account.
        "has_password": bool(user.password_hash),
        "google_linked": bool(user.google_sub),
        # Computed server-side from ADMIN_EMAILS. Only the signed-in owner sees
        # their own flag, and it is what reveals the Admin sidebar item.
        "is_admin": is_admin(user),
    }


def guard(request: Request, *policies: tuple[str, tuple[int, int]]) -> None:
    """Apply rate limits. `policies` are (key, (limit, window)) pairs."""
    for key, (limit, window) in policies:
        allowed, retry_after = limiter.allow(key, limit, window)
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=(
                    "Too many attempts. Please wait "
                    f"{retry_after} second{'s' if retry_after != 1 else ''} and try again."
                ),
                headers={"Retry-After": str(retry_after)},
            )


def send_or_fail(to: str, subject: str, body: str) -> None:
    """Hand one message to the provider, turning a failure into a clean 502.

    Every sign-up path sends through here, and that is not just tidiness: if
    only some of them raised on a mail failure, the status code alone would tell
    the caller which kind of address they had just submitted.
    """
    try:
        email_service.send_email(to, subject, body)
    except email_service.EmailError as exc:
        logger.warning("could not send email: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="We could not send the email just now. Please try again in a moment.",
        ) from exc


def send_code_or_fail(db: Session, user: User, purpose: OtpPurpose) -> int:
    """Issue a code and mail it. Returns the resend cooldown in seconds.

    If the mail cannot be sent the code is left in place (it is valid and
    unspent) and we answer 502, so the client can offer "resend" - better than
    pretending the email went out.
    """
    code = otp.issue_code(db, user, purpose)
    subject, body = email_service.otp_message(
        code, purpose.value, otp.CODE_TTL_MINUTES
    )
    send_or_fail(user.email, subject, body)
    return otp.RESEND_COOLDOWN_SECONDS


# --------------------------------------------------------------------------- #
# sign up
# --------------------------------------------------------------------------- #
@router.post("/auth/signup")
def signup(payload: SignupIn, request: Request, db: Session = Depends(get_db)):
    """Create an unverified account and email a code.

    The response is identical whether the address was free, already had an
    unverified account, or already had a verified one — so this endpoint cannot
    be used to test which emails are registered.
    """
    email = normalise_email(payload.email)
    guard(
        request,
        (f"signup:ip:{client_ip(request)}", SIGNUP_IP),
        (f"signup:email:{email or '-'}", SIGNUP_EMAIL),
    )

    error = validate_email(email) or validate_password(payload.password, email)
    if error:
        raise HTTPException(status_code=400, detail=error)

    existing = get_user_by_email(db, email)

    if existing is None:
        user = create_user(db, email, payload.password)
        send_code_or_fail(db, user, OtpPurpose.verify_email)
    elif existing.is_verified:
        # This address owns an account: tell them so, but hand out no code. The
        # submitted password is ignored entirely - signing up again must never
        # be a way to change an existing password.
        send_or_fail(
            existing.email,
            "You already have a Tenura account",
            (
                "Someone tried to sign up with this email address, but a "
                "Tenura account already exists for it.\n\n"
                "If that was you, use \"Log in\" and, if you have forgotten your "
                "password, \"Forgot password\" to reset it.\n\n"
                "If it was not you, you can ignore this email - nothing has "
                "changed.\n"
            ),
        )
    else:
        # Unverified account: an earlier code may still be live, so only send a
        # fresh one once the cooldown has passed.
        if otp.resend_wait(db, existing, OtpPurpose.verify_email) == 0:
            send_code_or_fail(db, existing, OtpPurpose.verify_email)

    # The same body for all three cases, and deliberately no field saying
    # whether a code actually went out - a "sent: true/false" would be a way to
    # ask the API "does this address already have an account?" one address at a
    # time. The sign-up page always moves to the code step, so it does not need
    # to know either.
    return {
        "status": "ok",
        "message": (
            "If that address can be registered, we have sent a 6-digit code to it. "
            "Enter it below to finish setting up your account."
        ),
        "email": email,
        "resend_in": otp.RESEND_COOLDOWN_SECONDS,
    }


# --------------------------------------------------------------------------- #
# verify
# --------------------------------------------------------------------------- #
@router.post("/auth/verify-otp")
def verify_otp(
    payload: VerifyOtpIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Spend a verification code, activate the account and sign the user in."""
    email = normalise_email(payload.email)
    guard(
        request,
        (f"otp:ip:{client_ip(request)}", OTP_IP),
        (f"otp:email:{email or '-'}", OTP_EMAIL),
    )

    user = get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=400, detail=_OTP_FAILURE)

    ok, _reason = otp.check_code(
        db, user, OtpPurpose.verify_email, (payload.code or "").strip()
    )
    if not ok:
        raise HTTPException(status_code=400, detail=_OTP_FAILURE)

    mark_verified(db, user)
    limiter.reset(f"otp:email:{email}")
    set_session_cookie(response, user)
    return {"status": "ok", "user": user_payload(user)}


@router.post("/auth/resend-otp")
def resend_otp(
    payload: ResendOtpIn, request: Request, db: Session = Depends(get_db)
):
    """Send a fresh code, subject to the 60-second cooldown.

    This endpoint must not be usable to test which addresses have an account, so
    every case - unknown address, known and unverified, known and verified, or a
    real account still inside its cooldown - answers with exactly the same body
    and the same status. Whether a code was actually sent is never observable:
    the cooldown is never echoed back (``resend_in`` is the constant window), and
    a mail failure for a real account is swallowed rather than raised, which
    would otherwise be a per-address signal via the status code.
    """
    email = normalise_email(payload.email)
    guard(request, (f"resend:ip:{client_ip(request)}", RESEND_IP))

    try:
        purpose = OtpPurpose(payload.purpose)
    except ValueError:
        purpose = OtpPurpose.verify_email

    user = get_user_by_email(db, email)
    # Only a genuine account that could receive one gets a code. The condition
    # is intentionally identical in effect to the old one; what changed is that
    # the caller can no longer tell which branch it took.
    if user is not None and not (
        purpose == OtpPurpose.verify_email and user.is_verified
    ):
        if otp.resend_wait(db, user, purpose) == 0:
            try:
                send_code_or_fail(db, user, purpose)
            except HTTPException:
                # A provider outage must not become a per-address signal.
                logger.warning("resend-otp: code could not be sent for a real account")

    return {
        "status": "ok",
        "message": "If that address can be registered, we have sent a new code.",
        "resend_in": otp.RESEND_COOLDOWN_SECONDS,
    }


# --------------------------------------------------------------------------- #
# log in / out
# --------------------------------------------------------------------------- #
@router.post("/auth/login")
def login(
    payload: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    email = normalise_email(payload.email)
    guard(
        request,
        (f"login:ip:{client_ip(request)}", LOGIN_IP),
        (f"login:email:{email or '-'}", LOGIN_EMAIL),
    )

    user = get_user_by_email(db, email)
    if user is None:
        # Same work as the real path, so timing does not leak existence.
        verify_password(_DUMMY_HASH, payload.password)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not verify_password(user.password_hash, payload.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    if not user.is_verified:
        # The password was correct, so this reveals nothing to anyone who does
        # not already know it — and it lets us offer to resend the code.
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": (
                    "This account still needs to be verified. We can send you a "
                    "new 6-digit code."
                ),
                "code": "unverified",
                "email": user.email,
            },
        )

    if needs_rehash(user.password_hash):
        set_password(db, user, payload.password)

    limiter.reset(f"login:email:{email}")
    set_session_cookie(response, user)
    return {"status": "ok", "user": user_payload(user)}


@router.post("/auth/logout")
def logout(response: Response):
    clear_session_cookie(response)
    return {"status": "ok"}


@router.get("/auth/me")
def me(user: User | None = Depends(get_current_user)):
    """Who is signed in, if anyone.

    Always 200 with `user: null` when signed out, so the header can render its
    logged-out state without a 401 in the browser console on every page load.

    `google` says whether "Continue with Google" is offered on this deployment,
    so the login and sign-up pages can show the button only when it would work.
    """
    return {
        "user": user_payload(user) if user else None,
        "google": google_auth.is_configured(),
    }


# --------------------------------------------------------------------------- #
# forgot password
# --------------------------------------------------------------------------- #
@router.post("/auth/forgot-password")
def forgot_password(payload: EmailIn, request: Request, db: Session = Depends(get_db)):
    """Email a reset code. Same generic answer whether or not the address exists."""
    email = normalise_email(payload.email)
    guard(
        request,
        (f"forgot:ip:{client_ip(request)}", FORGOT_IP),
        (f"forgot:email:{email or '-'}", FORGOT_EMAIL),
    )

    error = validate_email(email)
    if error:
        raise HTTPException(status_code=400, detail=error)

    user = get_user_by_email(db, email)
    if user is not None and otp.resend_wait(db, user, OtpPurpose.reset_password) == 0:
        try:
            send_code_or_fail(db, user, OtpPurpose.reset_password)
        except HTTPException:
            # Never let a mail problem turn a non-revealing endpoint into a
            # revealing one by failing only for real accounts.
            logger.warning("forgot-password: reset email could not be sent")

    return {
        "status": "ok",
        "message": (
            "If an account exists for that address, we have sent a 6-digit code "
            "to reset the password."
        ),
        "email": email,
        "resend_in": otp.RESEND_COOLDOWN_SECONDS,
    }


@router.post("/auth/reset-password")
def reset_password(
    payload: ResetPasswordIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """Spend a reset code, set the new password, and sign the user in.

    Receiving the code proves control of the address, so the account is marked
    verified too — that is how an unverified sign-up can be recovered from.
    """
    email = normalise_email(payload.email)
    guard(
        request,
        (f"otp:ip:{client_ip(request)}", OTP_IP),
        (f"otp:email:{email or '-'}", OTP_EMAIL),
    )

    user = get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status_code=400, detail=_OTP_FAILURE)

    ok, _reason = otp.check_code(
        db, user, OtpPurpose.reset_password, (payload.code or "").strip()
    )
    if not ok:
        raise HTTPException(status_code=400, detail=_OTP_FAILURE)

    # Validated only after the code is spent, so a weak password cannot be used
    # to probe whether an address has an account (or burn the code).
    error = validate_password(payload.password, email)
    if error:
        raise HTTPException(status_code=400, detail=error)

    set_password(db, user, payload.password)
    mark_verified(db, user)
    limiter.reset(f"otp:email:{email}")
    set_session_cookie(response, user)
    return {"status": "ok", "user": user_payload(user)}
