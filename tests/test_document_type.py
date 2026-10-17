"""
End-to-end test of RentCheck's document-type gate ("is this a tenancy
agreement?") using REAL sample documents plus generated gap-fillers.

It starts the real FastAPI app (uvicorn) and sends every fixture through the
real HTTP endpoints:

    POST /api/agreements/analyze         (pasted text)
    POST /api/agreements/analyze-upload  (PDF / .docx / image / .txt)

and compares the outcome with the expectation recorded in
``tests/fixtures/manifest.json``.

It then checks the failure paths (corrupt PDF, AI timeout, missing API key) all
return clean JSON rather than a bare 500.

Usage (from the repo root, with the app's normal environment/.env available):

    python tests/test_document_type.py

Regenerate the derived/generated fixtures first if needed:

    python tests/make_generated_fixtures.py

Exit code is non-zero if anything fails.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from contextlib import contextmanager
from urllib.parse import urlparse

import requests

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
MANIFEST = os.path.join(FIXTURES, "manifest.json")
BASE_PORT = 8150

# Small, obviously-a-lease text used for the failure-path tests (kept short so
# the AI-timeout test does not hammer many clauses).
ERROR_TEXT = (
    "TENANCY AGREEMENT. This lease is made between the Landlord and the Tenant "
    "for the premises. The tenant shall pay rent monthly. The landlord may "
    "re-enter if the rent is in arrears. The tenant shall keep the demised "
    "premises in repair. This tenancy agreement is governed by law."
)


def load_manifest() -> list[dict]:
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)["fixtures"]


@contextmanager
def run_server(env_overrides: dict | None = None, port: int = BASE_PORT):
    """Start uvicorn for the duration of the block."""
    env = os.environ.copy()
    if env_overrides:
        env.update(env_overrides)
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        deadline = time.time() + 60
        while time.time() < deadline:
            if proc.poll() is not None:
                raise RuntimeError("server exited during startup")
            try:
                if requests.get(f"{base}/health", timeout=2).status_code == 200:
                    break
            except requests.RequestException:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("server did not become ready")
        yield base
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


def content_type_for(name: str) -> str:
    ext = name.rsplit(".", 1)[-1].lower()
    return {
        "pdf": "application/pdf",
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "txt": "text/plain",
        "md": "text/plain",
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
    }.get(ext, "application/octet-stream")


def send(base: str, entry: dict) -> tuple[int, dict]:
    """Send one fixture and return (http_status, json_body)."""
    path = os.path.join(FIXTURES, entry["file"])
    name = os.path.basename(entry["file"])
    if entry["transport"] == "paste":
        text = open(path, encoding="utf-8", errors="ignore").read()
        r = requests.post(f"{base}/api/agreements/analyze", json={"text": text}, timeout=300)
    else:
        data = open(path, "rb").read()
        r = requests.post(
            f"{base}/api/agreements/analyze-upload",
            files={"file": (name, data, content_type_for(name))},
            timeout=300,
        )
    try:
        body = r.json()
    except ValueError:
        body = {"_raw": r.text[:200]}
    return r.status_code, body


def outcome_of(body: dict) -> str:
    """Map an API response to accept/reject for the gate."""
    status = body.get("status")
    if status == "ok":
        return "accept"
    return "reject"


def agreements_count(base: str) -> int | None:
    try:
        r = requests.get(f"{base}/health/db", timeout=10)
        if r.status_code == 200:
            return r.json().get("agreements")
    except requests.RequestException:
        pass
    return None


def run_manifest(base: str) -> tuple[bool, list[dict]]:
    fixtures = load_manifest()
    before = agreements_count(base)
    rows = []
    ok = True
    for entry in fixtures:
        http, body = send(base, entry)
        actual = outcome_of(body)
        passed = actual == entry["expected"]
        ok = ok and passed
        rows.append(
            {
                "file": entry["file"],
                "source": entry.get("source", ""),
                "expected": entry["expected"],
                "actual": actual,
                "detail": body.get("document_type") or body.get("detail") or "",
                "http": http,
                "pass": passed,
            }
        )
    after = agreements_count(base)
    if before is not None and after is not None:
        expected_accepts = sum(1 for e in fixtures if e["expected"] == "accept")
        delta = after - before
        persisted_ok = delta == expected_accepts
        print(
            f"\nPersistence check: agreements {before} -> {after} (delta {delta}); "
            f"{expected_accepts} accepted fixture(s) expected. "
            f"{'OK' if persisted_ok else 'MISMATCH (rejects may have been saved!)'}"
        )
        ok = ok and persisted_ok
    return ok, rows


def print_table(rows: list[dict]) -> None:
    w = max((len(r["file"]) for r in rows), default=10)
    print(f"\n{'fixture'.ljust(w)}  {'expected':8}  {'actual':8}  {'http':4}  result")
    print("-" * (w + 34))
    for r in rows:
        print(
            f"{r['file'].ljust(w)}  {r['expected']:8}  {r['actual']:8}  "
            f"{str(r['http']):4}  {'PASS' if r['pass'] else 'FAIL'}"
        )


def run_failure_paths() -> bool:
    """Corrupt PDF, AI timeout, missing API key -> clean JSON, never a bare 500."""
    print("\n=== Failure-path checks (must be clean JSON, never a bare 500) ===")
    ok = True

    # 1. Corrupt PDF (normal server).
    with run_server(port=BASE_PORT + 1) as base:
        r = requests.post(
            f"{base}/api/agreements/analyze-upload",
            files={"file": ("corrupt.pdf", b"%PDF-1.4\nthis is not a real pdf", "application/pdf")},
            timeout=60,
        )
        good = r.status_code < 500 and r.headers.get("content-type", "").startswith("application/json")
        ok = ok and good
        print(f"corrupt PDF          -> {r.status_code} {_short(r)}  [{'PASS' if good else 'FAIL'}]")

    # 2. Missing API key (real base URL, empty key -> upstream 401).
    with run_server({"RUMPTY_AI_KEY": ""}, port=BASE_PORT + 2) as base:
        r = requests.post(f"{base}/api/agreements/analyze", json={"text": ERROR_TEXT}, timeout=300)
        good = r.status_code < 500 and r.headers.get("content-type", "").startswith("application/json")
        ok = ok and good
        print(f"missing API key      -> {r.status_code} {_short(r)}  [{'PASS' if good else 'FAIL'}]")

    # 3. AI timeout (unroutable host, tiny timeout, no retries).
    with run_server(
        {"RUMPTY_AI_BASE_URL": "http://10.255.255.1:9/v1", "RUMPTY_AI_TIMEOUT": "2", "RUMPTY_AI_RETRIES": "0"},
        port=BASE_PORT + 3,
    ) as base:
        r = requests.post(f"{base}/api/agreements/analyze", json={"text": ERROR_TEXT}, timeout=300)
        good = r.status_code < 500 and r.headers.get("content-type", "").startswith("application/json")
        ok = ok and good
        print(f"AI timeout           -> {r.status_code} {_short(r)}  [{'PASS' if good else 'FAIL'}]")

    return ok


def _short(r: requests.Response) -> str:
    try:
        b = r.json()
    except ValueError:
        return r.text[:60]
    return json.dumps({k: b[k] for k in ("status", "detail") if k in b})[:70]


def main() -> int:
    db = os.environ.get("DATABASE_URL", "")
    host = urlparse(db).hostname if db else "(unset)"
    print(f"Using DATABASE_URL host: {host}  (run against the LOCAL db, not production)")
    with run_server() as base:
        ok, rows = run_manifest(base)
        print(f"Server: {base}")
    print_table(rows)
    ok = run_failure_paths() and ok

    total = len(rows)
    passed = sum(1 for r in rows if r["pass"])
    print(f"\nFixture gate: {passed}/{total} passed.")
    print("RESULT:", "ALL PASS" if ok else "FAILURES PRESENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
