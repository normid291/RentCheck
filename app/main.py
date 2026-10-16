import logging
import traceback
from contextlib import asynccontextmanager
from pathlib import Path

import requests as requests_lib
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from app.routers import agreements

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("rentcheck")

BASE_DIR = Path(__file__).resolve().parent


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Make the database ready before serving traffic.

    Creates missing tables, adds any columns missing from an older schema, and
    seeds clause_reference. This means a fresh or previously-uninitialised
    production database works without a separate manual init step. Failures are
    logged (with a full traceback) but do not stop the app from starting - the
    /health endpoint stays up and request-level errors are reported clearly.
    """
    try:
        from app.init_db import ensure_schema

        ensure_schema()
        logger.info("Database schema and seed data are ready.")
    except Exception:
        logger.error(
            "Database initialisation failed at startup:\n%s", traceback.format_exc()
        )
    yield


app = FastAPI(title="RentCheck", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten before final submission
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(agreements.router, prefix="/api", tags=["agreements"])


@app.get("/health")
def health():
    """Rumpty's readiness check hits this."""
    return {"status": "ok"}


@app.get("/health/db")
def health_db():
    """Diagnostic: can the app reach its database and query the tables?

    Separates a database/config problem from an application problem. Returns
    503 (not 200) when the database is unreachable or not initialised.
    """
    from app.database import engine
    from app.models.db import Agreement

    try:
        with engine.connect() as conn:
            count = conn.execute(select(func.count()).select_from(Agreement)).scalar()
        return {"status": "ok", "database": "reachable", "agreements": count}
    except Exception as exc:
        logger.error("Database health check failed:\n%s", traceback.format_exc())
        return JSONResponse(
            status_code=503,
            content={
                "status": "error",
                "database": "unreachable_or_uninitialised",
                "error": f"{type(exc).__name__}: {exc}",
            },
        )


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
                "Database error while saving the analysis. The service's "
                "database may be unreachable or not initialised."
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


# Serve the frontend (index.html + any static assets) at /. Mounted last so it
# does not shadow the API routes. Path is resolved relative to this file so it
# works regardless of the process working directory.
app.mount("/", StaticFiles(directory=str(BASE_DIR / "static"), html=True), name="static")
