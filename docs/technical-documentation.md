# Tenura Technical Documentation

Tenura is an AI-powered tenancy agreement analyzer for Nigerian renters. It takes a tenancy agreement by paste or upload and returns flagged clauses, missing protections, and questions to ask before signing, grounded in common Nigerian rental norms.

This document explains how to use the app, run it locally, and deploy it on Rumpty Cloud.

---

## 1. Using the app

### Analyse an agreement without an account

1. Open the site. The analyzer is on the home page.
2. Paste the agreement text, or upload a file. Supported formats are plain text, PDF, Word (.docx), and images of scanned pages.
3. Click Analyze.
4. Read the result:
   - Flagged clauses, each with the exact words quoted from the agreement.
   - Missing protections, such as a written receipt for the caution fee or a defined notice period.
   - Questions to ask before signing.
   - A coverage and risk summary.

You do not need an account to run an analysis. Nothing is stored unless you are signed in.

### What the app refuses to analyse

Two gates run before any clause analysis:

- Document-type gate: the input must be a tenancy agreement. A receipt, ID card, chat, or unrelated contract returns a clear message and is not stored.
- Jurisdiction gate: the agreement must be Nigerian. A clearly foreign agreement is refused rather than judged with Nigerian rules. If the country cannot be determined, the app asks you to name the Nigerian state or show the rent in naira.

Both cases return a normal response with an explanation, not an error page.

### Create an account and save your history

1. Go to Sign up and enter your email address and a password.
2. Enter the one-time code sent to that email.
3. After signing in you land on the dashboard. From there you can open My analyses, view a saved analysis, rename it, or delete it.
4. Sign-in with Google is available when the deployment has Google credentials configured.

All analyses are private to your account, and you can delete them at any time.

---

## 2. Run it locally

### Prerequisites

- Python 3.12
- PostgreSQL 14 or newer, running locally or reachable over the network
- Rumpty AI Inference credentials: base URL, API key, and model name
- Tesseract, if you want OCR for scanned PDFs and images
- Optional: a Resend API key for real sign-in emails, and Google OAuth credentials for Google sign-in

### Steps

1. Install the dependencies:

   pip install -r requirements.txt

2. Create your environment file:

   cp .env.example .env

3. Fill in .env. At minimum set DATABASE_URL and the three RUMPTY_AI variables. For local development also set:

   - SESSION_SECRET to any long random string
   - SESSION_COOKIE_SECURE=false, because a plain-http browser will not send a Secure-only cookie
   - EMAIL_PROVIDER=console, which prints sign-in codes to the server log instead of sending email

4. Create the schema and seed data:

   python -m app.init_db

   This creates missing tables, adds missing columns, applies the recorded migrations, and seeds the clause reference table. The same routine also runs on application startup, so a fresh database works without a separate step.

5. Start the server:

   uvicorn app.main:app --reload

6. Open http://localhost:8000.

### Environment variables

Required for analysis and accounts:

- DATABASE_URL: PostgreSQL connection string. Locally this points at your local Postgres. In production it points at the Neon database.
- SESSION_SECRET: signs the session cookie. Use at least 32 random characters in production. Without it, each restart generates a new key and signs every user out.
- RUMPTY_AI_BASE_URL: the AI Inference endpoint from the Rumpty console.
- RUMPTY_AI_KEY: the AI Inference API key.
- RUMPTY_AI_MODEL: the model name to call.

Email:

- EMAIL_PROVIDER: resend in production, console in development.
- RESEND_API_KEY: required when the provider is resend.
- EMAIL_FROM: the sender address, on a domain verified with Resend, in the form Tenura <no-reply@yourdomain.com>.

Production and optional:

- APP_ENV=production: enables the production startup checks and turns off the development email provider.
- SESSION_COOKIE_SECURE: leave unset in production so the default of true applies. Set to false only for local http work.
- GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET: optional. When both are set, the Continue with Google button appears.
- GOOGLE_REDIRECT_URI: optional. By default the redirect URI is derived from the incoming hostname.
- ALLOWED_ORIGINS: optional, comma-separated. The API is same-origin only by default.

---

## 3. Deploy on Rumpty Cloud

The repository contains a Dockerfile at the root, so Rumpty can build it directly.

1. Push the repository to GitHub.
2. In the Rumpty console, create a new Deployment and connect it to the repository. Choose main as the branch and Dockerfile as the build method.
3. Set the start command:

   uvicorn app.main:app --host 0.0.0.0 --port PORT

   Do not hardcode a port. The app must listen on the port Rumpty routes to. A build that listens on a different port succeeds but never becomes Active.
4. Set the readiness or health check path to /health. This endpoint returns a plain 200 and does not touch the database. The default / also works.
5. Add the environment variables from section 2 in the deployment configuration. At minimum set DATABASE_URL, SESSION_SECRET, APP_ENV=production, the email variables, and the three RUMPTY_AI variables.
6. Deploy and wait for the status to become Active. Open the generated app address.
7. Optionally attach a custom domain in the deployment settings.
8. If you use Google sign-in, add every hostname the app is served from as an Authorized redirect URI in the Google Cloud console. Each one needs its own entry:

   https://your-domain/api/auth/google/callback

   https://your-app.rumptycloud.app/api/auth/google/callback

### Database

Production uses a Neon PostgreSQL database. Copy the Neon connection string into DATABASE_URL in the Rumpty deployment configuration. The schema, columns, migrations, and clause reference seed are created automatically on startup, so no manual database step is needed after the first deploy.

To confirm the app can reach the database, call:

- GET /health returns 200 when the process is up.
- GET /health/db returns 200 with a status object when the database is reachable and initialised, or 503 with the actual error.

### Deploy checklist

- The start command binds the PORT variable, not a fixed port.
- The Port setting in the deployment matches the port the app binds.
- The readiness path is /health.
- SESSION_SECRET is set and at least 32 characters.
- APP_ENV is production.
- DATABASE_URL points at the Neon database.
- RESEND_API_KEY and EMAIL_FROM are set, and EMAIL_FROM uses a verified domain.
- The three RUMPTY_AI variables are set.
- Google redirect URIs include every hostname, if Google sign-in is enabled.

---

## 4. Troubleshooting

- Build succeeds but the deployment never becomes Active: the app is not listening on the port Rumpty expects. Bind the PORT variable and make sure the Port setting matches.
- Everyone is signed out after a restart: SESSION_SECRET is missing or too short. Set it in the deployment configuration.
- Sign-up or password reset fails: the email provider is not configured. Check EMAIL_PROVIDER, RESEND_API_KEY, and EMAIL_FROM.
- Saving an analysis returns 500: the database is unreachable or not initialised. Check DATABASE_URL and GET /health/db.
- Analysis returns 502: the AI Inference call failed. Check RUMPTY_AI_BASE_URL, RUMPTY_AI_KEY, and RUMPTY_AI_MODEL.
- The first request after an idle period is slow or returns 503: the app is cold-starting. The client retries transient failures automatically.
- A page still shows an old interface after a deploy: the app sends Cache-Control: no-cache for HTML, JS, and CSS and versions its asset URLs. A hard refresh clears any copy cached before that change.

---

## 5. Tests

Run the suite locally with:

- pip install -r requirements.txt -r requirements-dev.txt
- python -m app.init_db
- pytest
- ruff check app tests/unit tests/integration tests/conftest.py

Unit tests run without a database. Integration and end-to-end tests use a real PostgreSQL database. CI runs lint, type checks, and the full test suite on every push and pull request.
