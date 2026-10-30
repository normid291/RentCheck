"""Private owner dashboard API.

Both endpoints are hidden behind `require_admin`, which returns 404 for anyone
who is not a verified, allowlisted account. The rate limiter runs only after
that check, so an anonymous caller cannot distinguish a real admin route from a
missing one by watching for 429s.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.db import User
from app.services import admin_metrics
from app.services.auth import require_admin
from app.services.ratelimit import limiter, too_many

router = APIRouter(prefix="/admin")

ADMIN_API_LIMIT = 60
ADMIN_API_WINDOW = 60


def _rate_limit(request: Request, user: User) -> None:
    allowed, retry_after = limiter.allow(
        f"admin-api:{user.id}", ADMIN_API_LIMIT, ADMIN_API_WINDOW
    )
    if not allowed:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=too_many(retry_after)["detail"],
            headers={"Retry-After": str(retry_after)},
        )


@router.get("/metrics")
def metrics(
    request: Request,
    response: Response,
    range_key: str = Query("7d", alias="range"),
    refresh: bool = False,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _rate_limit(request, user)
    response.headers["Cache-Control"] = "no-store"
    return admin_metrics.get_metrics(db, range_key, force=refresh)


@router.get("/users")
def users(
    request: Request,
    response: Response,
    q: str = Query("", max_length=200),
    sort: str = Query("joined_desc"),
    page: int = Query(1, ge=1),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _rate_limit(request, user)
    response.headers["Cache-Control"] = "no-store"
    return admin_metrics.get_users(db, query=q, sort=sort, page=page)
