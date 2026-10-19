# RentCheck

AI-powered tenancy agreement analyzer for Nigerian renters. Paste or upload a
tenancy agreement and get back flagged clauses, missing protections, and
questions to ask before signing — grounded in common Nigerian rental norms.

Built for the Devcenter Hacktober sprint, deployed on Rumpty Cloud.

## Why it's built this way

Rumpty's AI Inference currently offers small open-source models (3B
parameters), not large general-purpose LLMs. Rather than asking the model to
reason freely about rental law — which small models do unreliably — RentCheck
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
- PostgreSQL (Rumpty Managed Database)
- Rumpty AI Inference (OpenAI-compatible endpoint)
- Plain HTML/JS frontend (no framework)
- Deployed via Rumpty App Deployments (GitHub-connected)

## Local setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Copy and fill in environment variables
cp .env.example .env
# edit .env with your local Postgres URL and Rumpty AI Inference credentials

# 3. Create the schema and seed data (also runs automatically on startup)
python -m app.init_db

# 4. Run the server
uvicorn app.main:app --reload
```

Visit `http://localhost:8000` to use the app.

`python -m app.init_db` creates any missing tables, adds any columns missing
from an older schema, and seeds `clause_reference`. The same routine runs on
app startup, so a fresh database is usable without extra steps.

## Deployment (Rumpty Cloud)

1. Push this repo to GitHub.
2. In the Rumpty console, create a new Deployment connected to this repo.
   The `Procfile` / `Dockerfile` start command is
   `uvicorn app.main:app --host 0.0.0.0 --port 8080`.
3. Set environment variables in the deployment config:
   - `DATABASE_URL` — the connection string for the Postgres instance the app
     should use (use the internal one when the app and DB are both on Rumpty)
   - `RUMPTY_AI_BASE_URL`, `RUMPTY_AI_KEY`, `RUMPTY_AI_MODEL` — from the AI Inference tab
4. The schema and seed data are created automatically on startup, so a manual
   `init_db` step is no longer required. To confirm the app can reach its
   database, call `GET /health/db` — it returns `200 {"status":"ok"...}` when the
   DB is reachable and initialised, or `503` with the actual error otherwise.

### API error responses

Failures return structured JSON (never a bare "Internal Server Error"):

| Status | When |
| ------ | ---- |
| 400 | Empty file, unsupported type, or a PDF/image with no readable text |
| 413 | Upload larger than 15 MB |
| 500 | Database error while saving the analysis (check `DATABASE_URL` + `/health/db`) |
| 502 | Upstream AI Inference unavailable |

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
notice. Output: `artifacts/rentcheck-demo.mp4`.

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium ffmpeg
python tests/make_demo_video.py            # records production
python tests/make_demo_video.py --url http://127.0.0.1:8000   # records locally
```

`tests/make_explainer_video.py` builds a stand-alone **motion-graphics explainer**
(no screen recording). It is driven by real data: `tests/export_explainer_data.py`
pulls an actual tenancy agreement from the database, runs it through the real
analysis pipeline, anonymises personal details and writes
`tests/fixtures/explainer_data.json`. The video then explains the flow
(problem -> add it -> analyse -> flagged -> report -> call to action) with clean
icons, short on-screen text, the brand palette/fonts, calm vertical/fade/scale
motion (nothing slides sideways), a professional voiceover (Edge neural TTS,
`en-US-AndrewNeural`) synced to the scenes, burned-in narration captions, and a
quiet ambient music bed that sidechain-ducks under the voice. Output:
`artifacts/rentcheck-explainer.mp4`.

```bash
python tests/export_explainer_data.py            # refresh real data (runs the pipeline)
python tests/export_explainer_data.py --no-run   # rebuild JSON from the stored analysis
python tests/make_explainer_video.py
python tests/make_explainer_video.py --voice en-GB-SoniaNeural --rate -2%  # alternate voice
python tests/make_explainer_video.py --no-music  # narration only
```

## Project structure

```
app/
  main.py                    - FastAPI app entrypoint
  database.py                - DB connection/session
  models/db.py                - SQLAlchemy models
  routers/agreements.py       - API endpoints
  services/clause_splitter.py - Deterministic clause splitting
  services/clause_matcher.py  - Deterministic clause-to-norm matching
  services/document_classifier.py - Is this a tenancy agreement? (gate before analysis)
  services/ai_inference.py    - Rumpty AI Inference calls (grounded, few-shot)
  services/protections.py     - Deterministic missing-protections + questions
  services/red_flags.py       - Deterministic high-confidence red-flag rules
  services/extractor.py       - PDF/Word/image/text upload -> plain text (pypdf, python-docx, OCR)
  seed_clause_reference.py    - Seed data for Nigerian rental norms
  static/index.html           - Frontend markup
  static/styles.css           - Frontend styles
  static/app.js               - Frontend logic
tests/
  test_document_type.py        - End-to-end gate tests over real + generated fixtures
  make_generated_fixtures.py   - Build derived scans / generated fixtures
  fetch_real_fixtures.py       - Re-download the real fixtures (network)
  fixtures/manifest.json       - Every fixture with its source URL + expected result
```

## Current scope

- **Paste text** or **upload a file** (PDF, Word `.docx`, image, or `.txt`) → analysis.
- A document-type gate runs first: non-tenancy inputs (receipts, photos, other
  contracts) and unreadable files are rejected with a friendly notice instead of
  being analysed (see below).
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

## Status

🚧 In active development — Devcenter Hacktober sprint, Oct 1-31 2026.
Weeks 1–3 complete: flagged clauses, missing protections + questions, and
PDF/image/text upload.
