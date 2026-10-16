from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.routers import agreements

app = FastAPI(title="RentCheck", version="0.1.0")

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


# Serve the frontend (index.html + any static assets) at /
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")
