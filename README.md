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

# 3. Create tables
python -m app.init_db

# 4. Seed clause reference data
python -m app.seed_clause_reference

# 5. Run the server
uvicorn app.main:app --reload
```

Visit `http://localhost:8000` to use the app.

## Deployment (Rumpty Cloud)

1. Push this repo to GitHub.
2. In the Rumpty console, create a new Deployment connected to this repo.
3. Set environment variables in the deployment config:
   - `DATABASE_URL` — internal connection string from your Rumpty Postgres instance
   - `RUMPTY_AI_BASE_URL`, `RUMPTY_AI_KEY`, `RUMPTY_AI_MODEL` — from the AI Inference tab
4. Build command: none needed (Python auto-detected). Start command:
   `uvicorn app.main:app --host 0.0.0.0 --port 8080`
5. After first deploy, run `python -m app.init_db` and
   `python -m app.seed_clause_reference` once via the Rumpty web terminal.

## Project structure

```
app/
  main.py                    - FastAPI app entrypoint
  database.py                - DB connection/session
  models/db.py                - SQLAlchemy models
  routers/agreements.py       - API endpoints
  services/clause_splitter.py - Deterministic clause splitting
  services/clause_matcher.py  - Deterministic clause-to-norm matching
  services/ai_inference.py    - Rumpty AI Inference calls (grounded, few-shot)
  services/protections.py     - Deterministic missing-protections + questions
  services/red_flags.py       - Deterministic high-confidence red-flag rules
  services/extractor.py       - PDF/image/text upload -> plain text (pypdf, OCR)
  seed_clause_reference.py    - Seed data for Nigerian rental norms
  static/index.html           - Frontend
```

## Current scope

- **Paste text** or **upload a file** (PDF, image, or `.txt`) → analysis.
- Outputs: flagged clauses, missing protections, and questions to ask before
  signing. Missing protections and questions are derived deterministically
  (`app/services/protections.py`) from which clause types were matched and
  which were flagged — no extra AI calls.
- Flags come from two sources: deterministic **rules** (`red_flags.py`, shown as
  "[flagged by rule]") which are certain, and the **AI** for everything else
  (shown as "[AI suggestion — worth a manual check]"). A rule match skips the
  AI call for that clause.
- Uploads are turned into text by `app/services/extractor.py`: `pypdf` for the
  PDF text layer, and Tesseract OCR for images. Photos of agreements work via
  OCR; scanned PDFs (no text layer) are rejected with a message asking for an
  image instead.

### Optional: image OCR

Image uploads need the Tesseract binary in addition to the Python packages:

- Windows: install from the [UB Mannheim build](https://github.com/UB-Mannheim/tesseract/wiki)
- macOS: `brew install tesseract`
- Debian/Ubuntu: `apt-get install tesseract-ocr`

If Tesseract is missing, PDF and text uploads still work, and image uploads
return a clear error rather than crashing. On Windows the default install
location is auto-detected; set `TESSERACT_CMD` in `.env` to override it.

## Status

🚧 In active development — Devcenter Hacktober sprint, Oct 1-31 2026.
Weeks 1–3 complete: flagged clauses, missing protections + questions, and
PDF/image/text upload.
