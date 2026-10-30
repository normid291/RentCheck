"""Aggregates for the owner-only admin dashboard.

Everything here is computed in Postgres with COUNT / GROUP BY / date_trunc and
returned as a small JSON object. No agreement text, clause content, model output
or document title is read. The users endpoint returns account basics only.

The metrics payload is cached for 60 seconds per range. The Refresh button asks
for `force=True`, which rebuilds the cache instead of waiting for expiry.
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import Date, cast, func, or_, select
from sqlalchemy.orm import Session

from app.models.db import AiRunEvent, Analysis, User

CACHE_SECONDS = 60
PER_PAGE = 20

_RANGE_KEYS = ("today", "7d", "30d", "all")
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_cache_lock = threading.Lock()


def _utcnow() -> datetime:
    """Naive UTC, matching the naive DateTime columns used by the app."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalise_range(value: str | None) -> str:
    candidate = (value or "7d").strip().lower()
    return candidate if candidate in _RANGE_KEYS else "7d"


def _range_start(key: str, now: datetime) -> datetime | None:
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if key == "today":
        return midnight
    if key == "7d":
        return midnight - timedelta(days=6)
    if key == "30d":
        return midnight - timedelta(days=29)
    return None


def _day_labels(start: datetime | None, now: datetime) -> list[str]:
    if start is None:
        return []
    first = start.date()
    last = now.date()
    days: list[str] = []
    current = first
    while current <= last:
        days.append(current.isoformat())
        current += timedelta(days=1)
    return days


def _status_bucket(status: str | None) -> str:
    if status == "success":
        return "success"
    if status == "rejected_non_nigerian":
        return "rejected"
    # Failed and (if ever used) rate-limited attempts are both unsuccessful.
    return "failed"


def _cache_get(key: str) -> dict[str, Any] | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry is None:
            return None
        expires, data = entry
        if expires <= time.monotonic():
            _cache.pop(key, None)
            return None
        return data


def _cache_set(key: str, data: dict[str, Any]) -> None:
    with _cache_lock:
        _cache[key] = (time.monotonic() + CACHE_SECONDS, data)


def clear_cache() -> None:
    """Used by tests and by the Refresh button's force path."""
    with _cache_lock:
        _cache.clear()


def get_metrics(
    db: Session, range_key: str | None = None, *, force: bool = False
) -> dict[str, Any]:
    key = normalise_range(range_key)
    if force:
        clear_cache()
    else:
        cached = _cache_get(key)
        if cached is not None:
            return cached

    data = _build_metrics(db, key)
    _cache_set(key, data)
    return data


def _build_metrics(db: Session, key: str) -> dict[str, Any]:
    now = _utcnow()
    start = _range_start(key, now)

    def in_range(query, column):
        if start is None:
            return query
        return query.filter(column >= start)

    total_users = int(db.query(func.count(User.id)).scalar() or 0)
    new_users = int(
        in_range(db.query(func.count(User.id)), User.created_at).scalar() or 0
    )
    saved_analyses = int(db.query(func.count(Analysis.id)).scalar() or 0)

    status_rows = (
        in_range(
            db.query(AiRunEvent.status, func.count(AiRunEvent.id)),
            AiRunEvent.created_at,
        )
        .group_by(AiRunEvent.status)
        .all()
    )
    status_counts = {str(status): int(count) for status, count in status_rows}
    total_runs = sum(status_counts.values())
    success_runs = status_counts.get("success", 0)
    rejected_runs = status_counts.get("rejected_non_nigerian", 0)
    rate_limited_runs = status_counts.get("rate_limited", 0)
    failed_runs = sum(
        count
        for status, count in status_counts.items()
        if status not in {"success", "rejected_non_nigerian"}
    )

    guest_runs = int(
        in_range(
            db.query(func.count(AiRunEvent.id)).filter(AiRunEvent.is_guest.is_(True)),
            AiRunEvent.created_at,
        ).scalar()
        or 0
    )
    logged_in_runs = max(0, total_runs - guest_runs)

    avg_duration = in_range(
        db.query(func.avg(AiRunEvent.duration_ms)).filter(
            AiRunEvent.duration_ms.isnot(None)
        ),
        AiRunEvent.created_at,
    ).scalar()
    avg_duration_ms = int(round(float(avg_duration))) if avg_duration is not None else None

    token_totals = in_range(
        db.query(
            func.coalesce(func.sum(AiRunEvent.input_tokens), 0),
            func.coalesce(func.sum(AiRunEvent.output_tokens), 0),
        ),
        AiRunEvent.created_at,
    ).one()
    input_tokens = int(token_totals[0] or 0)
    output_tokens = int(token_totals[1] or 0)

    # --- daily series -----------------------------------------------------
    # CAST(... AS DATE) avoids repeating date_trunc with separately-bound 'day'
    # parameters (Postgres treats those as different GROUP BY expressions).
    run_day = cast(AiRunEvent.created_at, Date)
    run_rows = (
        in_range(
            db.query(
                run_day.label("day"),
                AiRunEvent.status,
                func.count(AiRunEvent.id),
            ),
            AiRunEvent.created_at,
        )
        .group_by(run_day, AiRunEvent.status)
        .order_by(run_day)
        .all()
    )
    run_days: dict[str, dict[str, int]] = {}
    for day, status, count in run_rows:
        label = day.isoformat() if isinstance(day, date) else str(day)
        bucket = run_days.setdefault(
            label, {"success": 0, "failed": 0, "rejected": 0}
        )
        bucket[_status_bucket(status)] += int(count)

    run_labels = _day_labels(start, now) or sorted(run_days)
    ai_runs_daily = [
        {
            "date": label,
            "success": run_days.get(label, {}).get("success", 0),
            "failed": run_days.get(label, {}).get("failed", 0),
            "rejected": run_days.get(label, {}).get("rejected", 0),
        }
        for label in run_labels
    ]

    user_day = cast(User.created_at, Date)
    user_rows = (
        in_range(
            db.query(
                user_day.label("day"),
                func.count(User.id),
            ),
            User.created_at,
        )
        .group_by(user_day)
        .order_by(user_day)
        .all()
    )
    user_days = {
        (day.isoformat() if isinstance(day, date) else str(day)): int(count)
        for day, count in user_rows
    }
    user_labels = _day_labels(start, now) or sorted(user_days)
    new_users_daily = [
        {"date": label, "count": user_days.get(label, 0)} for label in user_labels
    ]

    # --- splits -----------------------------------------------------------
    method_query = in_range(db.query(func.count(User.id)), User.created_at)
    google_users = int(method_query.filter(User.google_sub.isnot(None)).scalar() or 0)
    signup_methods = {
        "google": google_users,
        "email": max(0, new_users - google_users),
    }

    source_rows = (
        in_range(
            db.query(AiRunEvent.source, func.count(AiRunEvent.id)),
            AiRunEvent.created_at,
        )
        .group_by(AiRunEvent.source)
        .all()
    )
    sources = {"paste": 0, "upload": 0, "sample": 0}
    for source, count in source_rows:
        sources[str(source or "unknown")] = int(count)

    return {
        "range": key,
        "start": _iso(start),
        "generated_at": _iso(now),
        "cached_for_seconds": CACHE_SECONDS,
        "totals": {
            "users": total_users,
            "new_users": new_users,
            "saved_analyses": saved_analyses,
            "runs": total_runs,
            "success_runs": success_runs,
            "success_rate": round((success_runs / total_runs) * 100, 1)
            if total_runs
            else 0.0,
            "guest_runs": guest_runs,
            "logged_in_runs": logged_in_runs,
            "failed_runs": failed_runs,
            "rejected_runs": rejected_runs,
            "rate_limited_runs": rate_limited_runs,
            "avg_duration_ms": avg_duration_ms,
        },
        "ai_runs_daily": ai_runs_daily,
        "new_users_daily": new_users_daily,
        "signup_methods": signup_methods,
        "sources": sources,
        "tokens": {"input": input_tokens, "output": output_tokens},
    }


def _display_name(email: str) -> str:
    local = (email or "").split("@", 1)[0]
    if not local:
        return "Account"
    cleaned = " ".join(local.replace(".", " ").replace("_", " ").replace("-", " ").split())
    return cleaned.title() if cleaned else "Account"


def get_users(
    db: Session,
    *,
    query: str = "",
    sort: str = "joined_desc",
    page: int = 1,
) -> dict[str, Any]:
    """A page of account basics. Deliberately never joins to agreement text."""
    term = (query or "").strip()[:200]
    filters = []
    if term:
        pattern = f"%{term}%"
        filters.append(
            or_(
                User.email.ilike(pattern),
                func.split_part(User.email, "@", 1).ilike(pattern),
            )
        )

    total = int(db.query(func.count(User.id)).filter(*filters).scalar() or 0)
    pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)
    current_page = max(1, min(int(page or 1), pages))

    analysis_count = (
        select(func.count(Analysis.id))
        .where(Analysis.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    analysis_last = (
        select(func.max(Analysis.created_at))
        .where(Analysis.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    event_last = (
        select(func.max(AiRunEvent.created_at))
        .where(AiRunEvent.user_id == User.id)
        .correlate(User)
        .scalar_subquery()
    )
    last_active = func.greatest(analysis_last, event_last).label("last_active")

    if sort == "joined_asc":
        order = (User.created_at.asc(), User.id.asc())
    elif sort == "analyses_desc":
        order = (analysis_count.desc(), User.created_at.desc())
    elif sort == "analyses_asc":
        order = (analysis_count.asc(), User.created_at.desc())
    else:
        order = (User.created_at.desc(), User.id.desc())

    rows = (
        db.query(
            User.id,
            User.email,
            User.created_at,
            User.google_sub,
            analysis_count.label("analysis_count"),
            last_active,
        )
        .filter(*filters)
        .order_by(*order)
        .limit(PER_PAGE)
        .offset((current_page - 1) * PER_PAGE)
        .all()
    )

    items = []
    for user_id, email, created_at, google_sub, count, active_at in rows:
        items.append(
            {
                "id": str(user_id),
                "name": _display_name(email),
                "email": email,
                "sign_up_method": "google" if google_sub else "email",
                "joined_at": _iso(created_at),
                "analysis_count": int(count or 0),
                "last_active": _iso(active_at),
            }
        )

    return {
        "items": items,
        "page": current_page,
        "per_page": PER_PAGE,
        "total": total,
        "pages": pages,
        "sort": sort if sort in {"joined_desc", "joined_asc", "analyses_desc", "analyses_asc"} else "joined_desc",
        "query": term,
    }
