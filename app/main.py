import logging
import os
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import requests as requests_lib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError

from app import config
from app.logging_config import configure_logging
from app.routers import agreements, auth, google_auth, history

configure_logging()
logger = logging.getLogger("tenura")

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Make the database ready before serving traffic.

    Creates missing tables, adds any columns missing from an older schema, and
    seeds clause_reference. This means a fresh or previously-uninitialised
    production database works without a separate manual init step. Failures are
    logged (with a full traceback) but do not stop the app from starting - the
    /health endpoint stays up and request-level errors are reported clearly.

    A misconfigured production process, by contrast, is refused outright: a bad
    SESSION_SECRET or an unconfigured mail provider must not serve one request.
    """
    # Deliberately outside the try: a production misconfiguration aborts startup.
    config.require_production_config()

    try:
        from app.init_db import ensure_schema

        ensure_schema()
        logger.info("Database schema and seed data are ready.")
    except Exception:
        logger.error(
            "Database initialisation failed at startup:\n%s", traceback.format_exc()
        )
    yield


app = FastAPI(
    title="Tenura",
    version="0.1.0",
    lifespan=lifespan,
    # Interactive docs are useful in development and a needless surface in
    # production, so they are simply not mounted there.
    docs_url=None if config.IS_PRODUCTION else "/docs",
    redoc_url=None if config.IS_PRODUCTION else "/redoc",
    openapi_url=None if config.IS_PRODUCTION else "/openapi.json",
)

# CORS is off by default: the front end is served from this same origin, so it
# needs nothing, and allow_origins=["*"] alongside cookie sessions would invite
# cross-site requests. Set ALLOWED_ORIGINS (comma separated) only if a separate
# origin genuinely has to call this API.
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in (os.environ.get("ALLOWED_ORIGINS") or "").split(",")
    if origin.strip()
]
if ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type"],
    )

app.include_router(agreements.router, prefix="/api", tags=["agreements"])
app.include_router(auth.router, prefix="/api", tags=["auth"])
app.include_router(google_auth.router, prefix="/api", tags=["auth"])
app.include_router(history.router, prefix="/api", tags=["history"])


@app.get("/health")
def health():
    """Liveness: the process is up and serving. Always 200.

    Deliberately does not touch the database. A platform readiness probe wants
    to know "should I keep sending this instance traffic", and a process that is
    alive but temporarily unable to reach the database should not be killed and
    restarted for it. Use /health/ready for the database-backed answer.
    """
    return {"status": "ok"}


@app.get("/health/ready")
def health_ready():
    """Readiness: can we actually serve a request (database reachable)?

    Returns 503 with a generic body when the database cannot be reached, so the
    endpoint cannot be used to fingerprint the deployment. The detail (exception
    type and message) goes to the server log only.
    """
    from app.database import engine
    from app.models.db import Agreement

    try:
        with engine.connect() as conn:
            # Bound the wait so a hung database cannot stall the probe.
            conn.execute(text("SET LOCAL statement_timeout = '3s'"))
            conn.execute(select(func.count()).select_from(Agreement)).scalar()
        return {"status": "ready"}
    except Exception:
        logger.error("Readiness check failed:\n%s", traceback.format_exc())
        return JSONResponse(status_code=503, content={"status": "not_ready"})


@app.get("/health/db")
def health_db():
    """Diagnostic alias for readiness. Kept for existing callers.

    Returns the same generic body as /health/ready: the exception detail stays
    in the server log rather than being handed to whoever can reach the URL.
    """
    return health_ready()


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    """Database failures -> clear JSON 500 and a full server-side traceback."""
    logger.error(
        "Database error on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={
            "detail": (
                "Database error while saving the analysis. Check that "
                "DATABASE_URL is set correctly for this deployment and that the "
                "database is reachable (see /health/db)."
            ),
            "error": type(exc).__name__,
        },
    )


@app.exception_handler(requests_lib.exceptions.RequestException)
async def upstream_error_handler(request: Request, exc):
    """Upstream AI Inference failures -> 502 (bad gateway)."""
    logger.error(
        "Upstream AI error on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=502,
        content={
            "detail": (
                "The AI analysis service is currently unavailable. "
                "Please try again in a moment."
            )
        },
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception):
    """Anything else -> JSON 500 instead of a bare 'Internal Server Error'."""
    logger.error(
        "Unhandled error on %s %s:\n%s",
        request.method,
        request.url.path,
        traceback.format_exc(),
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. The issue has been logged."},
    )


# Legal pages. Generated from docs/legal/*.md by scripts/build_legal_pages.py.
# Registered explicitly rather than left to the static mount resolving
# extensionless paths, so /privacy and /terms are guaranteed to resolve and are
# easy to find from the code.
@app.get("/privacy", include_in_schema=False)
def privacy_policy():
    return FileResponse(BASE_DIR / "static" / "privacy.html")


@app.get("/terms", include_in_schema=False)
def terms_of_service():
    return FileResponse(BASE_DIR / "static" / "terms.html")


# Account pages. Same reasoning as the legal pages: registered explicitly so
# /login, /signup and /history resolve without needing the ".html".
@app.get("/login", include_in_schema=False)
def login_page():
    return FileResponse(BASE_DIR / "static" / "login.html")


@app.get("/signup", include_in_schema=False)
def signup_page():
    return FileResponse(BASE_DIR / "static" / "signup.html")


@app.get("/history", include_in_schema=False)
def history_page():
    return FileResponse(BASE_DIR / "static" / "history.html")


@app.get("/dashboard", include_in_schema=False)
def dashboard_page():
    return FileResponse(BASE_DIR / "static" / "dashboard.html")


@app.get("/profile", include_in_schema=False)
def profile_page():
    return FileResponse(BASE_DIR / "static" / "profile.html")


# Serve the frontend (index.html + any static assets) at /. Mounted last so it
# does not shadow the API routes. Path is resolved relative to this file so it
# works regardless of the process working directory.
app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")
