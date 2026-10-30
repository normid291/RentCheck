# Tenura

AI-powered tenancy agreement analyzer for Nigerian renters. Paste or upload a
tenancy agreement and get back flagged clauses, missing protections, and
questions to ask before signing — grounded in common Nigerian rental norms.

No account is needed to run an analysis. Sign up (email plus a one-time code)
and your analyses are saved to a private history you can rename or delete at any
time.

Built for the Devcenter Hacktober sprint, deployed on Rumpty Cloud.

## Why it's built this way

Rumpty's AI Inference currently offers small open-source models (3B
parameters), not large general-purpose LLMs. Rather than asking the model to
reason freely about rental law — which small models do unreliably — Tenura
does the heavy lifting with deterministic code first:

1. **Clause splitting** (rule-based, no AI) — breaks the agreement into
   individual clauses.
2. **Clause matching** (keyword-based, no AI) — matches each clause against a
   curated `clause_reference` table of known Nigerian rental norms and
   red-flag patterns.
3. **Deterministic red-flag rules** — a small set of high-confidence regex
   rules (`app/services/red_flags.py`) catches well-known traps (e.g. re-entry
   "whether or not lawfully demanded", non-refundable caution fees). If a rule
   fires, its verdict is used directly and the AI call is skipped for that
   clause — so the most serious issues are never left to model chance.
4. **AI Inference** — called only for the clauses no rule caught, comparing one
   clause against its matched norm and returning a structured verdict, with
   few-shot examples to keep output format reliable. Every flag must quote
   exact words from the clause, which the code then verifies.

This keeps the AI's job small and well-defined, which is what small models
are actually good at.

## Stack

- FastAPI (Python) backend
- PostgreSQL (Neon in production; local Postgres for development)
- Rumpty AI Inference (OpenAI-compatible endpoint)
- Resend for transactional email (sign-in and password-reset codes)
- Plain HTML/JS frontend (no framework)
- Deployed via Rumpty App Deployments (GitHub-connected)

## Local setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in environment variables
cp .env.example .env
# edit .env with your local Postgres URL and Rumpty AI Inference credentials.
# For local work you also want:
#   SESSION_SECRET=<any long random string>   signs the session cookie
#   SESSION_COOKIE_SECURE=false               plain-http dev: the browser refuses
#                                             to send a Secure-only cookie
#   EMAIL_PROVIDER=console                    prints sign-in codes to the server
#                                             log instead of sending email

# 3. Create the schema, run migrations and seed data (also runs on startup)
python -m app.init_db

# 4. Run the server
uvicorn app.main:app --reload
```

Visit `http://localhost:8000` to use the app.

`python -m app.init_db` creates any missing tables, adds any columns missing
from an older schema, applies the recorded migrations in `app/migrations.py`,
and seeds `clause_reference`. The same routine runs on app startup, so a fresh
database is usable without extra steps.

### Schema changes

New tables are created from the models by `create_all()`. Anything `create_all`
cannot do to a table that already exists — adding a constraint or an index — is
written as an ordered, idempotent step in `app/migrations.py`, recorded in a
`schema_migrations` table so it runs once and is never repeated:

```python
MIGRATIONS: list[tuple[str, object]] = [
    ("0001_user_ownership", m0001_user_ownership),
    ("0002_google_signin", m0002_google_signin),
    ("0003_clause_provenance", m0003_clause_provenance),
]
```

Add a function and append it to the list; there is no separate migrate command
to remember. (`Procfile` starts uvicorn with no release phase, which is why this
runs on startup rather than through Alembic. The steps are small and
self-contained, so moving to Alembic later is mechanical.)

## Deployment (Rumpty Cloud)

1. Push this repo to GitHub.
2. In the Rumpty console, create a new Deployment connected to this repo and
   choose the **Dockerfile** build method (a `Dockerfile` sits at the repo root).
   The start command is `uvicorn app.main:app --host 0.0.0.0 --port $PORT`: the
   app binds whatever port Rumpty routes to and health-checks, and falls back to
   `8080` locally. Do **not** hardcode a port — a start command that listens on a
   different port than the deployment's **Port** setting is the most common
   reason a build succeeds but the deployment never becomes **Active**. Set the
   **Readiness/health check path** to `/health` (a plain `200` that never touches
   the database); the default `/` also works.
3. Set environment variables in the deployment config:
   - `DATABASE_URL` — the connection string for the Postgres instance the app
     should use. Production uses Neon; local development uses a local Postgres
     instance.
   - `SESSION_SECRET` — a long random string; signs the session cookie. Without
     it a random per-process key is generated, which signs everyone out on every
     restart (and a loud warning is printed). **Set this in production.**
   - `EMAIL_PROVIDER=resend`, `RESEND_API_KEY`, `EMAIL_FROM` — transactional
     email for sign-in codes. `EMAIL_FROM` must be on a domain verified with
     Resend, in the form `Tenura <no-reply@yourdomain.com>`. Without a
     provider, sign-up and password reset fail cleanly with a message telling
     the user the code could not be sent — no code is ever written to a log.
   - `APP_ENV=production` — refuses the development console email provider
     outright.
   - `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` — optional; turn on
     "Continue with Google" on the login and sign-up pages. See
     [Sign in with Google](#sign-in-with-google) below. If they are unset the
     button is not shown at all, so leaving them out is safe.
   - `SESSION_COOKIE_SECURE` — leave unset in production (the default, `true`,
     is what you want once the app is served over HTTPS).
   - `ALLOWED_ORIGINS` — optional, comma-separated. The API is same-origin only
     by default; add origins only if you deliberately serve the frontend from
     somewhere else.
   - `RUMPTY_AI_BASE_URL`, `RUMPTY_AI_KEY`, `RUMPTY_AI_MODEL` — from the AI Inference tab
4. The schema and seed data are created automatically on startup, so a manual
   `init_db` step is no longer required. To confirm the app can reach its
   database, call `GET /health/db` — it returns `200 {"status":"ok"...}` when the
   DB is reachable and initialised, or `503` with the actual error otherwise.

### Sign in with Google

Optional. Set `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` and the login and
sign-up pages grow a "Continue with Google" button; leave them out and the
button is not rendered at all and `/api/auth/google/start` answers `404`.

This uses the **server-side redirect** flow, not Google's JavaScript button. The
browser is sent to `accounts.google.com`, and Google returns it to
`/api/auth/google/callback` with a one-time code that *our server* exchanges for
the user's identity. Done this way, no Google script ever runs in our page and
no Google cookie is set on our domain — which is what keeps the privacy policy's
"no external scripts load on the page at all" true.

In the Google Cloud console, create an OAuth 2.0 client of type **Web
application** and add, as an *Authorized redirect URI*:

```
https://www.tenura.online/api/auth/google/callback
```

(A *JavaScript origin* is not used by this flow.) The URI is derived from the
hostname the visitor arrived on, so **each hostname the app is served from needs
its own entry** — both `www.tenura.online` and the `*.rumptycloud.app` address.
Alternatively pin one with `GOOGLE_REDIRECT_URI`, which is only safe if every
hostname points at that same value.

What the code guarantees:

- an account created this way has **no password** (`users.password_hash` is
  `NULL`), and password login refuses it with the usual generic message until the
  user sets one through "Forgot password";
- signing in with Google on an address that already has an email/password
  account **links** the two and marks it verified, because Google has already
  proved the address — the existing password keeps working;
- an account is matched by Google's stable account id first and by verified
  email second; Google must report `email_verified`, so a token claiming an
  unverified address is refused;
- CSRF is covered by a signed, httpOnly, ten-minute `state` cookie and the code
  exchange uses PKCE, so a callback that is not the one we started is refused
  with the same generic "please try again" message as every other failure.

### API error responses

Failures return structured JSON (never a bare "Internal Server Error"):

| Status | When |
| ------ | ---- |
| 400 | Empty file, unsupported type, or a PDF/image with no readable text; also a bad email address or a too-short password |
| 401 | No session, or the session expired (sign-in required) |
| 403 | The password was right but the email is not verified yet (`{"detail":{"code":"unverified"}}`) |
| 413 | Upload larger than 15 MB |
| 429 | Rate limit hit on sign-up, log in, or a code request |
| 500 | Database error while saving the analysis (check `DATABASE_URL` + `/health/db`) |
| 502 | Upstream AI Inference unavailable, or a sign-in code could not be sent |

Full stack traces are always logged server-side.

### Document-type gate (is this even a tenancy agreement?)

Before anything is analysed, `app/services/document_classifier.py` decides what
the input actually is, for every path (paste, PDF, image, `.txt`, `.docx`):

- `tenancy_agreement` — proceed with the clause analysis.
- `not_tenancy_agreement` — e.g. a receipt, ID card, chat, photo or another
  contract type.
- `unreadable` — too blurry/dark or too little text to judge.

Most inputs are decided deterministically (text volume + tenancy keywords), so a
clear lease or a clear non-lease costs **no extra AI call**. Two rules keep that
fast path honest:

- **Title signal.** A deterministic *accept* requires at least one tenancy
  keyword in the document's head (~first 400 chars), because real agreements
  name themselves ("DEED OF LEASE", "ASSURED SHORTHOLD TENANCY AGREEMENT",
  "LICENCE TO OCCUPY", "CONTRAT DE LOCATION"). A finance/employment contract
  that only mentions "lease"/"landlord" deep in its body is not waved through.
- **Language awareness.** Keywords cover English, French (`bail`, `locataire`),
  Spanish (`arrendamiento`) and German (`Mietvertrag`) tenancy forms, and any
  text with a meaningful run of accented/non-Latin letters is sent to the model
  rather than being rejected on English keywords it never had.

Only genuinely ambiguous text reaches the model (one call) to return
`{document_type, confidence, reason}`. If that call fails, the title signal is
used as the fallback (a document that never names itself as a tenancy is
rejected) instead of failing the request.

When the verdict is not a tenancy agreement, the API returns a **clean 200**
(not an error) and does **not** write an `Agreement`/`Analysis` row, so rejected
uploads never count as completed analyses:

```json
{
  "status": "not_a_tenancy_agreement",
  "document_type": "not_tenancy_agreement",
  "confidence": 0.9,
  "reason": "an unrelated document",
  "message": "This doesn't look like a tenancy agreement. It looks like an unrelated document. Please upload your actual tenancy agreement, lease, or rental contract.",
  "flagged_clauses": [],
  "missing_protections": [],
  "questions_to_ask": []
}
```

`status` is `unreadable` for that case; successful analyses return
`"status": "ok"` with `"document_type": "tenancy_agreement"`.

### Jurisdiction gate (which country's norms apply?)

Tenura reviews **Nigerian** tenancy agreements against Nigerian norms, so after
the document-type gate it decides the jurisdiction
(`app/services/jurisdiction.py`) and **never silently judges a foreign
agreement with Nigerian rules**:

- `NG-LA`, `NG-FC`, `NG-<CODE>`, `NG-UNKNOWN` — Nigerian; judged with the NG
  norm pack.
- `NON_NG` — clearly from another country. A **clean 200**
  (`"status": "out_of_scope"`) with no analysis and **nothing stored**.
- `UNKNOWN` — not enough signal. A **clean 200**
  (`"status": "needs_jurisdiction"`) asking the user to name the Nigerian state
  or show the rent in naira.

The decision is deterministic first (the naira sign, Nigerian states/cities and
law names versus `£`, "assured shorthold", "section 21", `€`, French/German/
Spanish tenancy words, `$`), with **one** model call only when the text is
genuinely ambiguous and the answer `UNKNOWN` (ask the user) when it is still
unsure. Agreement text is treated as untrusted data: instructions embedded in it
are ignored (see `docs/legal/jurisdiction-notes.md`).

### Coverage and risk banding

Every clause that is matched to a norm is checked; `coverage` is the fraction of
the agreement's clauses that actually got a verdict. The risk band is derived
deterministically from the flagged/missing counts **and the coverage**
(`app/services/scoring.py`): a run that checked too little, or whose model calls
failed, is reported as **`unknown` / "Review needed"** with a plain-language
coverage note — it is **never** shown as "low risk". Sufficiently covered runs
band as low / moderate / high.

### Where the norms come from — and what they are not

The norms in `clause_reference` are seeded with `legal_basis = "market_norm"`:
they state **common practice in the Nigerian rental market, not the law**. Their
source fields are deliberately empty and **no statute or section number is
invented**. The UI therefore says "common practice in Nigeria", never "the law
requires". `docs/legal/source-register.md` lists every norm and the process a
lawyer follows to promote one to `legal_basis = "statute"`.

## Testing the document gate

`tests/` holds an end-to-end harness that runs the real HTTP endpoints against
**real, publicly available sample documents** (Nigerian deeds of lease, UK
assured shorthold tenancies, a US lease, a French bail, plus employment / loan /
NDA / sale contracts, a news article and generated invoices/photos). Every
fixture and its expected outcome is recorded with its source URL in
`tests/fixtures/manifest.json`.

```bash
python tests/make_generated_fixtures.py   # (re)build derived scans + generated fixtures
python tests/test_document_type.py        # run everything; exits non-zero on any failure
```

The runner starts the app with uvicorn, sends each fixture through
`/api/agreements/analyze` (paste) or `/api/agreements/analyze-upload`
(PDF / `.docx` / image / `.txt`), prints a pass/fail table, checks that rejected
inputs are **not** persisted, and verifies the failure paths (corrupt PDF, AI
timeout, missing API key) return clean JSON instead of a bare 500.

Regenerate the real downloads with `tests/fetch_real_fixtures.py` (network
required); the fixtures themselves are committed.

### Demo video

`tests/make_demo_video.py` records a short walkthrough of the live app with a
real browser (Playwright): it loads the page, analyses the sample agreement,
tours the results, then shows the "this doesn't look like a tenancy agreement"
notice. Output: `artifacts/tenura-demo.mp4`.

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium ffmpeg
python tests/make_demo_video.py            # records production
python tests/make_demo_video.py --url http://127.0.0.1:8000   # records locally
```

`tests/make_explainer_video.py` builds a stand-alone **premium SaaS-style
explainer** (no screen recording): a dark brand-gradient stage, flat-
illustration characters (a tenant and an agent), floating glass UI cards, stage
labels ("01 - UPLOAD"), an app-window results screen, animated stat numbers and
subtitle-style captions. Motion is calm and vertical (fades, gentle scale,
bobbing - nothing slides sideways).

It is driven by real data: `tests/export_explainer_data.py` pulls an actual
tenancy agreement from the database, runs it through the real analysis
pipeline, anonymises personal details and writes
`tests/fixtures/explainer_data.json` (flagged clauses, severities, the evidence
quote, counts and the questions to ask). The "Flagged", "Report" and "What to
ask" scenes all render that real output; the report scene is shown as an actual
app window containing the real result cards. A professional voiceover (Edge
neural TTS, `en-US-AndrewNeural`) is synced to the scenes, with burned-in
narration captions and a quiet ambient music bed that sidechain-ducks under the
voice. Output: `artifacts/tenura-explainer.mp4`.

```bash
python tests/export_explainer_data.py            # refresh real data (runs the pipeline)
python tests/export_explainer_data.py --no-run   # rebuild JSON from the stored analysis
python tests/make_explainer_video.py
python tests/make_explainer_video.py --vertical  # also write a 9:16 social cut
python tests/make_explainer_video.py --voice en-GB-SoniaNeural --rate -2%  # alternate voice
python tests/make_explainer_video.py --no-music  # narration only
```

## Testing accounts and history

`tests/test_accounts.py` drives the real app through FastAPI's `TestClient`
against whatever `DATABASE_URL` points at. It covers the whole flow and the rules
around it:

- a guest analysis succeeds and **stores nothing**;
- sign-up emails a code and answers identically whether the address was free,
  unverified or already registered;
- a wrong code and an unknown address return byte-for-byte the same error;
- the right code verifies the account and signs the user in;
- a signed-in analysis is saved, listed, opened, renamed and deleted — and
  deleting it removes the agreement text from the database;
- another account gets a `404` for all four operations on it;
- passwords are stored as argon2id, never in plain text;
- log out, log in, the unverified-account block, forgot/reset password;
- OTP single use, the 5-wrong-attempts cap, and the 60-second resend cooldown.

Email is stubbed in memory and the per-clause AI call is stubbed with a fixed
verdict, so the test is fast, offline and deterministic. Clause splitting,
clause matching, flagging, authentication, sessions and persistence all run for
real. It cleans up every account it creates.

```bash
python tests/test_accounts.py
```

## Testing Google sign-in

`tests/test_google_signin.py` covers "Continue with Google" the same way. Google
is the only thing stubbed (`fetch_identity`); the state cookie, the callback's
checks, account creation and linking, and the session all run for real. The
token-claim rules are tested directly against `identity_from_id_token` with
hand-built JWTs, so nothing touches the network.

- a token with the wrong audience, issuer, expiry, or an unverified email is
  refused;
- `/api/auth/me` reports whether Google sign-in is available, and `/start` is a
  `404` when it is not;
- `/start` redirects to Google with `state` and PKCE `S256`, and sets an httpOnly
  handoff cookie;
- a callback with a wrong, missing, or reused-by-another-client state is refused
  with the generic error, and hands out no session;
- a new Google sign-in creates a verified account with **no password**, and
  password login then refuses it;
- signing in again with the same Google account reuses that account;
- Google sign-in on an existing email/password account links it, verifies it, and
  leaves the password working;
- a second Google account cannot claim an address already linked to another.

```bash
python tests/test_google_signin.py
```

## Project structure

```
app/
  main.py                    - FastAPI app entrypoint
  database.py                - DB connection/session
  models/db.py                - SQLAlchemy models (User, OtpCode, Analysis, ...)
  migrations.py               - Ordered, idempotent schema steps (see "Schema changes")
  init_db.py                  - create tables + columns + migrations + seed
  routers/agreements.py       - Analyse endpoints (persist only when signed in)
  routers/auth.py             - Sign up, verify, resend, log in/out, forgot/reset
  routers/google_auth.py      - "Continue with Google": /auth/google/start + /callback
  routers/history.py          - List, open, rename, delete your own analyses
  services/clause_splitter.py - Deterministic clause splitting
  services/clause_matcher.py  - Deterministic clause-to-norm matching per jurisdiction
  services/document_classifier.py - Is this a tenancy agreement? (gate before analysis)
  services/jurisdiction.py    - Which country's (and which Nigerian state's) norms apply?
  services/scoring.py         - Coverage, degraded flag, and risk banding (never "low" on thin runs)
  services/ai_inference.py    - Rumpty AI Inference calls (grounded, few-shot)
  services/protections.py     - Deterministic missing-protections + questions
  services/red_flags.py       - Deterministic high-confidence red-flag rules
  services/extractor.py       - PDF/Word/image/text upload -> plain text (pypdf, python-docx, OCR)
  services/auth.py            - argon2id hashing, signed session cookie, dependencies
  services/google_auth.py     - Google OAuth redirect flow, ID-token claim checks
  services/otp.py             - One-time codes: issue, verify, attempts, cooldown
  services/email.py           - Resend + console providers, OTP message
  services/ratelimit.py       - In-memory sliding-window rate limiter
  services/analysis_store.py  - Ownership-scoped save/list/open/rename/delete
  seed_clause_reference.py    - Seed data for Nigerian rental norms
  static/common.js            - Shared window.Tenura helpers: apiFetch (cold-start
                                retry), header session, renderers, pending store
  static/index.html           - Frontend markup
  static/styles.css           - Frontend styles
  static/app.js               - Analyser logic + guest "keep this" flow
  static/signup.html/.js      - Create account + enter code
  static/login.html/.js       - Log in, forgot password, verify, reset
  static/history.html/.js     - Saved analyses: list, detail, rename, delete
  static/privacy.html         - Privacy Policy page (generated — see docs/legal)
  static/terms.html           - Terms of Service page (generated)
tests/
  conftest.py                  - shared fixtures (client, make_user, captured_email)
  unit/                        - fast, DB-free unit tests (red flags, jurisdiction,
                                 matching, scoring, evidence, redaction, health)
  integration/                 - DB-backed tests (resend enumeration, jurisdiction gate)
  test_accounts.py             - End-to-end accounts + history test
  test_google_signin.py        - End-to-end "Continue with Google" test
  test_document_type.py        - End-to-end gate tests over real + generated fixtures
  make_generated_fixtures.py   - Build derived scans / generated fixtures
  fetch_real_fixtures.py       - Re-download the real fixtures (network)
  fixtures/manifest.json       - Every fixture with its source URL + expected result
docs/
  legal/                       - Privacy policy + terms, source register, jurisdiction notes
  legal/source-register.md     - Every clause norm and its (unverified) legal basis
  legal/jurisdiction-notes.md  - How jurisdiction is detected and gated
scripts/
  build_legal_pages.py         - Renders docs/legal/*.md into the pages the app serves
```

### Automated tests (CI)

`.github/workflows/ci.yml` runs on every push and pull request against a
Postgres service: `ruff` (lint), `mypy` (the annotated modules), then `pytest`
(unit + integration). Run the same locally:

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m app.init_db      # schema + seed for the integration tests
pytest                     # or: pytest tests/unit  (no database needed)
ruff check app tests/unit tests/integration tests/conftest.py
```

## Current scope

- **Paste text** or **upload a file** (PDF, Word `.docx`, image, or `.txt`) → analysis.
- **No account required.** A guest gets the full analysis; nothing about the
  document is stored, and the result is offered a "keep this" sign-up prompt
  afterwards.
- **Accounts** (email + password + a 6-digit code) with a private **history**:
  analyses run while signed in are saved automatically, listed newest first, and
  can be renamed or deleted — deleting removes the agreement text too. Only a
  signed-in owner can reach their own records.
- A document-type gate runs first: non-tenancy inputs (receipts, photos, other
  contracts) and unreadable files are rejected with a friendly notice instead of
  being analysed (see below).
- A jurisdiction gate runs next: a clearly non-Nigerian agreement is refused
  (`out_of_scope`) and an ambiguous one asks the user (`needs_jurisdiction`);
  neither is stored. Only `NG-*` agreements are judged against Nigerian norms.
- Every result carries a **coverage** figure and a **risk band**; a run that
  checked too few clauses is shown as "Review needed", never "low risk".
- Outputs: flagged clauses, missing protections, and questions to ask before
  signing. Missing protections and questions are derived deterministically
  (`app/services/protections.py`) from which clause types were matched and
  which were flagged — no extra AI calls.
- Flags come from two sources: deterministic **rules** (`red_flags.py`, shown as
  "[flagged by rule]") which are certain, and the **AI** for everything else
  (shown as "[AI suggestion — worth a manual check]"). A rule match skips the
  AI call for that clause.
- Uploads are turned into text by `app/services/extractor.py`: `pypdf` for the
  PDF text layer, `python-docx` for Word documents, and Tesseract OCR for
  images. Scanned PDFs with no text layer are rasterised with `pypdfium2` and
  OCR'd too (capped at the first 25 pages). Photos of agreements work via OCR.
  Legacy `.doc` files are not supported — save them as `.docx` or PDF first.

### Supported upload formats

| Format | Extensions | Read by |
|--------|------------|---------|
| PDF | `.pdf` | `pypdf` text layer; scanned PDFs fall back to `pypdfium2` + OCR |
| Word | `.docx` | `python-docx` |
| Image | `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff` | Tesseract OCR |
| Plain text | `.txt`, `.md` | direct decode (UTF-8/UTF-16/Latin-1) |

### Optional: OCR (images and scanned PDFs)

OCR needs the Tesseract binary in addition to the Python packages:

- Windows: install from the [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki)
- macOS: `brew install tesseract`
- Debian/Ubuntu: `apt-get install tesseract-ocr`

If Tesseract is missing, PDF (text layer), Word and text uploads still work;
image uploads and scanned PDFs return a clear error rather than crashing. On
Windows the default install location is auto-detected; set `TESSERACT_CMD` in
`.env` to override it.

## Legal pages

The privacy policy and terms of service are served by the app at `/privacy` and
`/terms`, and linked from the footer of the main page.

The Markdown in `docs/legal/` is the single source. The HTML the app serves is
generated from it — edit the Markdown, never the HTML:

```bash
python scripts/build_legal_pages.py
```

Both documents describe what the code actually does (which clauses reach the AI,
what is stored, that rejected uploads are dropped), so they need updating when
that behaviour changes. `docs/legal/README.md` lists what is still to be filled
in — the registered address, where the hosting and AI providers actually run —
and flags that neither document has been reviewed by a lawyer yet.

## Status

🚧 In active development — Devcenter Hacktober sprint, Oct 1-31 2026.
Weeks 1–3 complete: flagged clauses, missing protections + questions, and
PDF/image/text upload. Accounts, one-time-code sign-in and per-user analysis
history are now in place, with the guest flow unchanged: analyse without an
account, save it once you have one.
