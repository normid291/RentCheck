"""End-to-end test for "Continue with Google".

Drives the real app through TestClient. Google itself is not reachable (and must
not be, in a test), so the single call that talks to Google — `fetch_identity` —
is stubbed. Everything else is real: the state cookie, the callback's checks,
account creation and linking, the session cookie and the database.

The token-claim validation is tested directly against `identity_from_id_token`,
with hand-built JWTs, so the rules that decide whose account you land on are
exercised without a network round trip.

    python tests/test_google_signin.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
import time
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient

from app.services import google_auth
from app.services.ratelimit import limiter

# Outbound email is stubbed for the same reason the AI call is in the accounts
# test: this runs offline and must not depend on a provider being configured.
from app.services import email as email_service  # noqa: E402

SENT: list[dict] = []


def _capture_email(to, subject, body):
    SENT.append({"to": to, "subject": subject, "body": body})


email_service.send_email = _capture_email

from app.database import SessionLocal  # noqa: E402
from app.main import app  # noqa: E402
from app.models.db import Agreement, Analysis, OtpCode, User  # noqa: E402

CLIENT_ID = "test-client-id.apps.googleusercontent.com"
PASSWORD = "correct-horse-battery"

FAILURES: list[str] = []


def check(label: str, condition, extra: str = "") -> None:
    ok = bool(condition)
    print(("  PASS  " if ok else "  FAIL  ") + label + ("" if ok else f"   [{extra}]"))
    if not ok:
        FAILURES.append(label)


def b64(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def id_token(**claims) -> str:
    """A JWT shaped the way Google's ID token is. The signature is never checked
    (see the service docstring), so a placeholder third segment is enough."""
    base = {
        "aud": CLIENT_ID,
        "iss": "https://accounts.google.com",
        "exp": int(time.time()) + 600,
        "email_verified": True,
        "email": "someone@example.com",
        "sub": "1234567890",
    }
    base.update(claims)
    return f"{b64({'alg': 'RS256', 'typ': 'JWT'})}.{b64(base)}.signature-not-verified"


def main() -> int:
    limiter.clear()

    google_auth.CLIENT_ID = CLIENT_ID
    google_auth.CLIENT_SECRET = "test-client-secret"
    google_auth.REDIRECT_URI = ""

    # Google is the only thing stubbed.
    identities: dict[str, dict] = {}
    real_fetch = google_auth.fetch_identity

    def fake_fetch_identity(code, redirect_uri, code_verifier):
        if code not in identities:
            raise google_auth.GoogleAuthError("simulated Google failure")
        return identities[code]

    google_auth.fetch_identity = fake_fetch_identity

    created: list[str] = []
    client = TestClient(app, base_url="https://testserver")

    def start_and_state(next_path: str = "") -> str:
        """Hit /start and pull the state out of the Location it returns."""
        url = "/api/auth/google/start"
        if next_path:
            url += "?next=" + next_path
        response = client.get(url, follow_redirects=False)
        assert response.status_code == 303, response.text
        location = response.headers["location"]
        assert "state=" in location, location
        return location.split("state=")[1].split("&")[0]

    try:
        print("\n[1] The ID token decides whose account this is")
        try:
            identity = google_auth.identity_from_id_token(id_token(sub="42", email="A@Example.com"))
            check("a valid token yields sub and a normalised email",
                  identity["sub"] == "42" and identity["email"] == "a@example.com", str(identity))
        except google_auth.GoogleAuthError as exc:
            check("a valid token yields sub and a normalised email", False, str(exc))

        for label, claims in (
            ("wrong audience", {"aud": "some-other-app"}),
            ("wrong issuer", {"iss": "https://evil.example"}),
            ("expired", {"exp": int(time.time()) - 3600}),
            ("unverified email", {"email_verified": False}),
            ("string 'false' is not true", {"email_verified": "false"}),
            ("no subject", {"sub": ""}),
            ("no email", {"email": ""}),
        ):
            try:
                google_auth.identity_from_id_token(id_token(**claims))
                check(f"rejects a token with {label}", False, "accepted")
            except google_auth.GoogleAuthError:
                check(f"rejects a token with {label}", True)

        print("\n[2] The pages are told whether Google sign-in is available")
        check("with credentials set, /me says google: true",
              client.get("/api/auth/me").json().get("google") is True)
        google_auth.CLIENT_SECRET = ""
        check("with no credentials, /me says google: false",
              client.get("/api/auth/me").json().get("google") is False)
        check("and /start is a 404",
              client.get("/api/auth/google/start", follow_redirects=False).status_code == 404)
        google_auth.CLIENT_SECRET = "test-client-secret"

        print("\n[3] Starting the flow sends you to Google, with state and PKCE")
        response = client.get("/api/auth/google/start?next=/history", follow_redirects=False)
        location = response.headers["location"]
        check("it is a redirect to accounts.google.com",
              response.status_code == 303 and location.startswith("https://accounts.google.com/"), location[:60])
        check("the client id is present", f"client_id={CLIENT_ID}" in location)
        check("the redirect uri points at our callback",
              "redirect_uri=https%3A%2F%2Ftestserver%2Fapi%2Fauth%2Fgoogle%2Fcallback" in location)
        check("a state is sent", "&state=" in location)
        check("PKCE S256 is used",
              "code_challenge_method=S256" in location and "code_challenge=" in location)
        check("the handoff cookie is httpOnly",
              "HttpOnly" in response.headers.get("set-cookie", ""))
        check("the handoff cookie is the one we expect",
              "tenura_oauth=" in response.headers.get("set-cookie", ""))

        print("\n[4] A callback that is not ours is refused")
        state = start_and_state()
        bad = client.get("/api/auth/google/callback?code=x&state=wrong", follow_redirects=False)
        check("a state that does not match redirects to the login page with an error",
              bad.status_code == 303 and bad.headers["location"].startswith("/login?error=google"),
              bad.headers.get("location", ""))
        check("and no session was set", "tenura_session=" not in bad.headers.get("set-cookie", ""))

        client.cookies.clear()
        no_cookie = client.get(f"/api/auth/google/callback?code=x&state={state}", follow_redirects=False)
        check("a callback with no handoff cookie is refused too",
              no_cookie.status_code == 303 and no_cookie.headers["location"].startswith("/login?error=google"))

        check("a Google-side failure ('access_denied') is refused",
              client.get("/api/auth/google/callback?error=access_denied&state=" + start_and_state(),
                         follow_redirects=False).headers["location"].startswith("/login?error=google"))

        print("\n[5] A real callback creates the account and signs the user in")
        fresh = f"tenura-google-{uuid.uuid4().hex[:10]}@example.com"
        created.append(fresh)
        identities["code-new"] = {"sub": f"google-{uuid.uuid4().hex[:8]}", "email": fresh, "name": "New Person"}
        state = start_and_state("/history")
        landed = client.get(f"/api/auth/google/callback?code=code-new&state={state}", follow_redirects=False)
        check("it redirects to the page that was asked for",
              landed.status_code == 303 and landed.headers["location"] == "/history",
              landed.headers.get("location", ""))
        check("a session cookie is set", "tenura_session=" in landed.headers.get("set-cookie", ""))
        me = client.get("/api/auth/me").json()
        check("the browser is now signed in", me["user"] and me["user"]["email"] == fresh, str(me)[:120])

        db = SessionLocal()
        row = db.query(User).filter(User.email == fresh).one()
        check("the account exists and has no password",
              row.password_hash is None, repr(row.password_hash)[:60])
        check("it is marked verified", bool(row.is_verified))
        check("the Google id is stored", bool(row.google_sub))
        gsub = row.google_sub
        check("there is still just one account for the address",
              db.query(User).filter(User.email == fresh).count() == 1)
        db.close()

        check("password login is refused, and says nothing",
              client.post("/api/auth/login",
                          json={"email": fresh, "password": PASSWORD}).status_code == 401)

        print("\n[6] Signing in again with the same Google account reuses it")
        client.post("/api/auth/logout")
        identities["code-again"] = {"sub": gsub, "email": fresh, "name": "New Person"}
        state = start_and_state()
        again = client.get(f"/api/auth/google/callback?code=code-again&state={state}", follow_redirects=False)
        check("it signs in again", again.status_code == 303 and again.headers["location"] == "/")
        check("it is the same account, not a second one",
              client.get("/api/auth/me").json()["user"]["email"] == fresh)
        db = SessionLocal()
        check("no duplicate row was created",
              db.query(User).filter(User.email == fresh).count() == 1)
        db.close()

        print("\n[7] An existing email/password account is linked, not duplicated")
        linked = f"tenura-google-link-{uuid.uuid4().hex[:8]}@example.com"
        created.append(linked)
        client.post("/api/auth/logout")
        signup = client.post("/api/auth/signup", json={"email": linked, "password": PASSWORD})
        check("a password account is created", signup.status_code == 200, signup.text[:120])
        db = SessionLocal()
        before = db.query(User).filter(User.email == linked).one()
        check("it starts unverified", not before.is_verified)
        db.close()

        identities["code-link"] = {"sub": f"google-{uuid.uuid4().hex[:8]}", "email": linked, "name": "Linked"}
        state = start_and_state()
        linked_back = client.get(f"/api/auth/google/callback?code=code-link&state={state}", follow_redirects=False)
        check("the Google sign-in succeeds", linked_back.status_code == 303, linked_back.text[:120])
        db = SessionLocal()
        after = db.query(User).filter(User.email == linked).one()
        check("the account was linked, not replaced",
              after.id == before.id and after.google_sub == identities["code-link"]["sub"])
        check("and the existing password is untouched",
              after.password_hash is not None and after.password_hash == before.password_hash)
        check("linking verified the address Google vouched for", bool(after.is_verified))
        db.close()
        client.post("/api/auth/logout")
        check("the original password still works",
              client.post("/api/auth/login",
                          json={"email": linked, "password": PASSWORD}).status_code == 200)

        print("\n[8] A second Google account cannot claim an already-linked address")
        client.post("/api/auth/logout")
        identities["code-thief"] = {"sub": f"other-{uuid.uuid4().hex[:8]}", "email": linked, "name": "Someone else"}
        state = start_and_state()
        stolen = client.get(
            f"/api/auth/google/callback?code=code-thief&state={state}", follow_redirects=False
        )
        check("it is refused with the generic failure",
              stolen.headers["location"].startswith("/login?error=google"), stolen.headers.get("location", ""))
        check("and no session was handed out", "tenura_session=" not in stolen.headers.get("set-cookie", ""))

        print("\n[9] A callback that fails at Google is refused cleanly")
        state = start_and_state()
        failed = client.get(f"/api/auth/google/callback?code=does-not-exist&state={state}", follow_redirects=False)
        check("an unusable code redirects to the login page with an error",
              failed.headers["location"].startswith("/login?error=google"), failed.headers.get("location", ""))
        check("and no session was set", "tenura_session=" not in failed.headers.get("set-cookie", ""))

    finally:
        google_auth.fetch_identity = real_fetch
        print("\n[10] Cleaning up test accounts")
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
