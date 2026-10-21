"""End-to-end smoke test for accounts and analysis history.

Drives the real FastAPI app through TestClient against whatever database
DATABASE_URL points at, so it exercises the same code the browser hits:
sign up -> OTP -> sessions -> analyse -> history -> rename -> delete, plus the
rules around each of those (generic errors, ownership, OTP limits).

Two things are stubbed so the test is fast, offline and deterministic:
  - outbound email, which is captured in memory so the test can read the code
  - the per-clause AI call, which needs the Rumpty service and is not what this
    test is about (clause splitting, matching and flagging still run for real)

It cleans up every account it creates. Run from the repo root:

    python tests/test_accounts.py
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.services import email as email_service
from app.services.ratelimit import limiter

# --------------------------------------------------------------------------- #
# stubs
# --------------------------------------------------------------------------- #
SENT: list[dict] = []


def _capture_email(to, subject, body):
    SENT.append({"to": to, "subject": subject, "body": body})


email_service.send_email = _capture_email

from app.routers import agreements as agreements_router  # noqa: E402
from app.services.document_classifier import TENANCY_AGREEMENT  # noqa: E402


def _always_tenancy(text, source_type):
    return {"document_type": TENANCY_AGREEMENT, "confidence": 0.95, "reason": ""}


def _fake_analyze_clause(clause_text, reference):
    """One predictable high-severity flag, so the result is never empty."""
    if reference.clause_type == "re_entry_forfeiture":
        return {
            "flag": True,
            "clause_type": "re_entry_forfeiture",
            "severity": "high",
            "reason": "The landlord can re-enter immediately on arrears.",
            "evidence": " ".join(clause_text.split())[:70],
            "source": "ai",
            "clause": clause_text,
        }
    return {"flag": False}


agreements_router.classify_document = _always_tenancy
agreements_router.analyze_clause = _fake_analyze_clause

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.db import Agreement, Analysis, OtpCode, User  # noqa: E402

_FIXTURE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "fixtures", "real", "ng_deed_text.txt"
)

AGREEMENT = ""
try:
    with open(_FIXTURE, encoding="utf-8") as _fh:
        AGREEMENT = _fh.read()
except OSError:
    AGREEMENT = (
        "TENANCY AGREEMENT\n"
        "1. The tenancy is for a term of two years.\n"
        "2. TO PAY all taxes, rates, duties and outgoings in respect of the premises.\n"
        "3. If any part of the rent is in arrears for 21 days, whether or not lawfully "
        "demanded, the Landlord may re-enter the premises and the term shall "
        "absolutely cease and determine.\n"
    )

PASSWORD = "correct-horse-battery"
NEW_PASSWORD = "a-different-password-42"

FAILURES: list[str] = []


def check(label: str, condition, extra: str = "") -> None:
    ok = bool(condition)
    print(("  PASS  " if ok else "  FAIL  ") + label + ("" if ok else f"   [{extra}]"))
    if not ok:
        FAILURES.append(label)


def code_from_last_email() -> str:
    match = re.search(r"\b(\d{6})\b", SENT[-1]["body"])
    assert match, "no 6-digit code in the captured email"
    return match.group(1)


def signup_and_verify(client, email: str, password: str = PASSWORD) -> str:
    SENT.clear()
    response = client.post("/api/auth/signup", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    code = code_from_last_email()
    verified = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
    assert verified.status_code == 200, verified.text
    return code


def main() -> int:
    limiter.clear()  # otherwise a previous run's counters limit this one

    client = TestClient(app, base_url="https://testserver")
    email = f"tenura-e2e-{uuid.uuid4().hex[:10]}@example.com"
    other_email = f"tenura-e2e-other-{uuid.uuid4().hex[:8]}@example.com"
    unverified_email = f"tenura-e2e-unv-{uuid.uuid4().hex[:8]}@example.com"
    otp_email = f"tenura-e2e-otp-{uuid.uuid4().hex[:8]}@example.com"
    created = [email, other_email, unverified_email, otp_email]

    try:
        print("\n[1] A guest can analyse, and nothing is stored")
        db = SessionLocal()
        before = (db.query(Agreement).count(), db.query(Analysis).count())
        db.close()

        body = client.post("/api/agreements/analyze", json={"text": AGREEMENT}).json()
        check("guest result is not saved", body.get("saved") is False, json.dumps(body)[:160])
        check("guest result has no analysis id", body.get("analysis_id") is None)
        check("guest still gets a risk score", isinstance(body.get("risk_score"), int))
        check("history needs a session", client.get("/api/analyses").status_code == 401)

        db = SessionLocal()
        after = (db.query(Agreement).count(), db.query(Analysis).count())
        db.close()
        check("the guest run wrote no agreement row", after[0] == before[0], f"{before[0]} -> {after[0]}")
        check("the guest run wrote no analysis row", after[1] == before[1], f"{before[1]} -> {after[1]}")

        print("\n[2] Sign up is generic and emails a code")
        SENT.clear()
        response = client.post("/api/auth/signup", json={"email": email, "password": PASSWORD})
        check("signup returns 200", response.status_code == 200, response.text[:160])
        check("one email was sent", len(SENT) == 1, str(len(SENT)))
        check("the email carries a 6-digit code", bool(re.search(r"\b\d{6}\b", SENT[-1]["body"])))
        check("password is nowhere in the email", PASSWORD not in SENT[-1]["body"])
        code = code_from_last_email()

        # The address now definitely exists. Signing up again must answer the
        # same way, and must not let anyone set a new password.
        _mangled = client.post(
            "/api/auth/signup", json={"email": email, "password": "attacker-chosen-password"}
        )
        check("re-signup gives the same status", _mangled.status_code == response.status_code)
        # The whole body, not just the message: any field that varied here - "was
        # a code actually sent?", say - would let the sign-up form be used to
        # test which addresses already have accounts.
        check(
            "re-signup gives an identical response body",
            _mangled.json() == response.json(),
            f"{response.json()} vs {_mangled.json()}",
        )
        check("no field says whether a code went out", "sent" not in response.json())
        check(
            "the attacker's password was not accepted",
            client.post(
                "/api/auth/login", json={"email": email, "password": "attacker-chosen-password"}
            ).status_code == 401,
        )

        print("\n[3] Input validation")
        check(
            "bad email rejected",
            client.post("/api/auth/signup", json={"email": "nope", "password": PASSWORD}).status_code == 400,
        )
        check(
            "short password rejected",
            client.post(
                "/api/auth/signup",
                json={"email": f"x{uuid.uuid4().hex[:6]}@example.com", "password": "short"},
            ).status_code == 400,
        )

        print("\n[4] A bad code is refused, and says nothing about the account")
        wrong = client.post("/api/auth/verify-otp", json={"email": email, "code": "000000"})
        unknown = client.post(
            "/api/auth/verify-otp",
            json={"email": f"ghost-{uuid.uuid4().hex[:8]}@example.com", "code": "000000"},
        )
        check("wrong code is 400", wrong.status_code == 400)
        check(
            "an unknown email answers exactly like a wrong code",
            unknown.status_code == wrong.status_code and unknown.json() == wrong.json(),
        )

        print("\n[5] The right code verifies the account and signs the user in")
        verified = client.post("/api/auth/verify-otp", json={"email": email, "code": code})
        check("verify returns 200", verified.status_code == 200, verified.text[:160])
        check("a session cookie was set", "tenura_session" in client.cookies)
        me = client.get("/api/auth/me").json()
        check("me returns the signed-in user", me["user"] and me["user"]["email"] == email)
        check("the user payload carries no hash", "password_hash" not in json.dumps(me))

        print("\n[6] A signed-in analysis is saved")
        body = client.post("/api/agreements/analyze", json={"text": AGREEMENT}).json()
        analysis_id = body.get("analysis_id")
        check("saved flag is true", body.get("saved") is True)
        check("an analysis id came back", bool(analysis_id))
        check("a title was derived", bool(body.get("title")), str(body.get("title")))
        check("a recommendation was derived", bool(body.get("recommendation")))

        print("\n[7] It appears in history")
        listing = client.get("/api/analyses").json()
        check("history returns 200", listing.get("status") == "ok")
        check("exactly one analysis", listing["count"] == 1, str(listing["count"]))
        item = listing["analyses"][0]
        check("the newest is first", item["id"] == analysis_id)
        check("it carries a risk band", item["risk_level"] in ("low", "medium", "high"))

        print("\n[8] Open, rename, and open again")
        detail = client.get(f"/api/analyses/{analysis_id}").json()["analysis"]
        check("detail includes the findings", "flagged_clauses" in detail)
        check("detail includes an agreement preview", "agreement_preview" in detail)
        check("detail does not ship the whole document", "raw_text" not in detail)
        renamed = client.patch(f"/api/analyses/{analysis_id}", json={"title": "Ado-Ekiti flat"})
        check("rename returns 200", renamed.status_code == 200)
        check(
            "the new title stuck",
            client.get(f"/api/analyses/{analysis_id}").json()["analysis"]["title"] == "Ado-Ekiti flat",
        )

        print("\n[9] Another account cannot reach it")
        other = TestClient(app, base_url="https://testserver")
        signup_and_verify(other, other_email)
        check("someone else's analysis is a 404", other.get(f"/api/analyses/{analysis_id}").status_code == 404)
        check("their history is empty", other.get("/api/analyses").json()["count"] == 0)
        check(
            "they cannot rename it",
            other.patch(f"/api/analyses/{analysis_id}", json={"title": "mine now"}).status_code == 404,
        )
        check("they cannot delete it", other.delete(f"/api/analyses/{analysis_id}").status_code == 404)
        check("it survived all of that", client.get(f"/api/analyses/{analysis_id}").status_code == 200)

        print("\n[10] Password hashing")
        db = SessionLocal()
        stored = db.query(User).filter(User.email == email).one()
        check("the hash is argon2id", stored.password_hash.startswith("$argon2id$"), stored.password_hash[:20])
        check("the plaintext is not stored", PASSWORD not in stored.password_hash)
        db.close()

        print("\n[11] Log out, then log in")
        client.post("/api/auth/logout")
        check("signed out", client.get("/api/auth/me").json()["user"] is None)
        check("history is closed again", client.get("/api/analyses").status_code == 401)

        bad = client.post("/api/auth/login", json={"email": email, "password": "wrong-password"})
        ghost = client.post(
            "/api/auth/login",
            json={"email": f"ghost-{uuid.uuid4().hex[:8]}@example.com", "password": "wrong-password"},
        )
        check("wrong password is 401", bad.status_code == 401)
        check("the message is generic", bad.json()["detail"] == "Invalid email or password.")
        check(
            "an unknown email is indistinguishable from a wrong password",
            ghost.status_code == bad.status_code and ghost.json() == bad.json(),
        )
        check("correct password logs in", client.post(
            "/api/auth/login", json={"email": email, "password": PASSWORD}
        ).status_code == 200)

        print("\n[12] An unverified account is blocked, and offered a code")
        SENT.clear()
        client.post("/api/auth/signup", json={"email": unverified_email, "password": PASSWORD})
        blocked = client.post("/api/auth/login", json={"email": unverified_email, "password": PASSWORD})
        check("unverified login is 403", blocked.status_code == 403, blocked.text[:160])
        check("the client is told why", blocked.json()["detail"].get("code") == "unverified")
        check(
            "it did not hand out a session",
            blocked.cookies.get("tenura_session") is None,
        )

        print("\n[13] Forgot password")
        SENT.clear()
        check(
            "forgot-password returns 200",
            client.post("/api/auth/forgot-password", json={"email": email}).status_code == 200,
        )
        check("a reset code was emailed", len(SENT) == 1, str(len(SENT)))
        reset_code = code_from_last_email()
        reset = client.post(
            "/api/auth/reset-password",
            json={"email": email, "code": reset_code, "password": NEW_PASSWORD},
        )
        check("reset returns 200", reset.status_code == 200, reset.text[:160])
        client.post("/api/auth/logout")
        check(
            "the old password no longer works",
            client.post("/api/auth/login", json={"email": email, "password": PASSWORD}).status_code == 401,
        )
        check(
            "the new password works",
            client.post("/api/auth/login", json={"email": email, "password": NEW_PASSWORD}).status_code == 200,
        )

        SENT.clear()
        anon = client.post(
            "/api/auth/forgot-password", json={"email": f"ghost-{uuid.uuid4().hex[:8]}@example.com"}
        )
        check("forgot-password is generic for unknown addresses", anon.status_code == 200)
        check("nothing was emailed for an unknown address", len(SENT) == 0)

        print("\n[14] OTP limits")
        SENT.clear()
        signup_client = TestClient(app, base_url="https://testserver")
        signup_client.post("/api/auth/signup", json={"email": otp_email, "password": PASSWORD})
        first_code = code_from_last_email()
        check(
            "resending inside the cooldown is refused",
            signup_client.post("/api/auth/resend-otp", json={"email": otp_email}).status_code == 429,
        )
        wrong_code = "111111" if first_code != "111111" else "222222"
        for _ in range(5):
            signup_client.post("/api/auth/verify-otp", json={"email": otp_email, "code": wrong_code})
        check(
            "the correct code is refused after 5 wrong attempts",
            signup_client.post(
                "/api/auth/verify-otp", json={"email": otp_email, "code": first_code}
            ).status_code == 400,
        )

        # Wind the cooldown back rather than sleeping for a minute.
        db = SessionLocal()
        person = db.query(User).filter(User.email == otp_email).one()
        for row in db.query(OtpCode).filter(OtpCode.user_id == person.id).all():
            row.created_at = row.created_at - timedelta(seconds=61)
        db.commit()
        db.close()

        SENT.clear()
        check(
            "resending is allowed once the cooldown has passed",
            signup_client.post("/api/auth/resend-otp", json={"email": otp_email}).status_code == 200,
        )
        second_code = code_from_last_email()
        check(
            "the replacement code works",
            signup_client.post(
                "/api/auth/verify-otp", json={"email": otp_email, "code": second_code}
            ).status_code == 200,
        )
        check(
            "and cannot be used twice",
            signup_client.post(
                "/api/auth/verify-otp", json={"email": otp_email, "code": second_code}
            ).status_code == 400,
        )

        print("\n[15] A broken mail provider fails the same way for every address")
        # If only some sign-up paths raised on a mail failure, the status code
        # alone would reveal whether the address was brand new or already
        # registered. Every path has to fail identically.
        limiter.clear()
        fresh_email = f"tenura-e2e-mail-{uuid.uuid4().hex[:8]}@example.com"
        created.append(fresh_email)

        def _failing_send(to, subject, body):
            raise email_service.EmailError("simulated provider outage")

        real_send = email_service.send_email
        email_service.send_email = _failing_send
        try:
            free = client.post(
                "/api/auth/signup", json={"email": fresh_email, "password": PASSWORD}
            )
            known = client.post(
                "/api/auth/signup", json={"email": email, "password": PASSWORD}
            )
        finally:
            email_service.send_email = real_send

        check("a mail failure is a 502 for a new address", free.status_code == 502, free.text[:120])
        check("a mail failure is a 502 for a registered address", known.status_code == 502, known.text[:120])
        check(
            "the two failures are indistinguishable",
            free.json() == known.json(),
            f"{free.text[:90]} vs {known.text[:90]}",
        )

        print("\n[16] Delete removes the analysis and its agreement text")
        db = SessionLocal()
        row = db.get(Analysis, uuid.UUID(analysis_id))
        agreement_id = row.agreement_id
        db.close()

        check("delete returns 200", client.delete(f"/api/analyses/{analysis_id}").status_code == 200)
        check("history is now empty", client.get("/api/analyses").json()["count"] == 0)
        check("re-opening it is a 404", client.get(f"/api/analyses/{analysis_id}").status_code == 404)

        db = SessionLocal()
        check("the agreement text is gone for good", db.get(Agreement, agreement_id) is None)
        db.close()

    finally:
        print("\n[17] Cleaning up test accounts")
        db = SessionLocal()
        try:
            for address in created:
                user = db.query(User).filter(User.email == address).first()
                if not user:
                    continue
                for analysis in db.query(Analysis).filter(Analysis.user_id == user.id).all():
                    agreement = db.get(Agreement, analysis.agreement_id)
                    db.delete(analysis)
                    if agreement is not None:
                        db.delete(agreement)
                db.query(OtpCode).filter(OtpCode.user_id == user.id).delete()
                db.delete(user)
            db.commit()
        finally:
            db.close()
        print("  done")

    print("\n" + ("=" * 60))
    if FAILURES:
        print(f"{len(FAILURES)} check(s) FAILED:")
        for label in FAILURES:
            print("  - " + label)
        return 1
    print("All checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
