"""Recorded, idempotent schema migrations.

Why this instead of Alembic
    This service is deployed straight from the Procfile with no release phase:
    the container starts and uvicorn serves. A migration step that has to be run
    by hand is therefore a step that will eventually be forgotten, and the deploy
    that forgot it is the one that breaks. `ensure_schema()` already exists (and
    runs on every boot) for exactly that reason, so the new schema work lives
    here: ordered steps, each recorded in `schema_migrations` once applied, each
    written to be safe to run twice.

    If you would rather use Alembic, this is the piece to replace — nothing else
    depends on it beyond the single call in `app/init_db.py`.

What actually needs a "migration" rather than `create_all()`
    `create_all()` creates missing TABLES but never touches existing ones, and
    `add_missing_columns()` adds missing COLUMNS but not the constraints or
    indexes behind them. On a database that already has an `analyses` table, the
    new `user_id` column therefore arrives without its foreign key or index —
    that is what step 0001 fixes.
"""
from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from app.database import engine

_FK_ANALYSES_USER = "fk_analyses_user_id_users"
_FK_OTP_USER = "fk_otp_codes_user_id_users"


def _fk_names(conn: Connection, table: str) -> set[str]:
    return {fk.get("name") for fk in inspect(conn).get_foreign_keys(table)}


def _index_names(conn: Connection, table: str) -> set[str]:
    return {ix.get("name") for ix in inspect(conn).get_indexes(table)}


def _column_names(conn: Connection, table: str) -> set[str]:
    return {col["name"] for col in inspect(conn).get_columns(table)}


def _has_table(conn: Connection, table: str) -> bool:
    return inspect(conn).has_table(table)


def m0001_user_ownership(conn: Connection) -> list[str]:
    """Give the account tables their foreign keys and the history query its index.

    Every check is against the live database, so this is safe on a brand-new
    database (where create_all() has already done the work and there is nothing
    to add) and on an existing one (where it does the work).
    """
    notes: list[str] = []

    if _has_table(conn, "analyses") and _has_table(conn, "users"):
        columns = _column_names(conn, "analyses")
        if "user_id" in columns:
            if _FK_ANALYSES_USER not in _fk_names(conn, "analyses"):
                conn.execute(
                    text(
                        "ALTER TABLE analyses ADD CONSTRAINT "
                        f"{_FK_ANALYSES_USER} FOREIGN KEY (user_id) "
                        "REFERENCES users(id) ON DELETE CASCADE"
                    )
                )
                notes.append(f"added {_FK_ANALYSES_USER}")
            # The history page filters on user_id and sorts by created_at. A
            # plain index on user_id is enough at this scale and is what the
            # model asks for, so the two never disagree.
            if "ix_analyses_user_id" not in _index_names(conn, "analyses"):
                conn.execute(
                    text("CREATE INDEX ix_analyses_user_id ON analyses (user_id)")
                )
                notes.append("added index ix_analyses_user_id")

    if _has_table(conn, "otp_codes") and _has_table(conn, "users"):
        columns = _column_names(conn, "otp_codes")
        if "user_id" in columns and _FK_OTP_USER not in _fk_names(conn, "otp_codes"):
            conn.execute(
                text(
                    "ALTER TABLE otp_codes ADD CONSTRAINT "
                    f"{_FK_OTP_USER} FOREIGN KEY (user_id) "
                    "REFERENCES users(id) ON DELETE CASCADE"
                )
            )
            notes.append(f"added {_FK_OTP_USER}")

    return notes


# Order matters: run top to bottom, only the unapplied ones.
MIGRATIONS: list[tuple[str, object]] = [
    ("0001_user_ownership", m0001_user_ownership),
]


def run_migrations() -> list[str]:
    """Apply any unrecorded migrations. Returns the names applied this run.

    Each migration gets its own transaction, and a failure is logged and skipped
    rather than raised: a broken migration must not stop the app from booting
    (the /health endpoint and the rest of the schema sync should still come up),
    and because nothing is recorded it is retried on the next start.
    """
    applied: list[str] = []

    with engine.begin() as conn:
        conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS schema_migrations ("
                "  name VARCHAR(120) PRIMARY KEY,"
                "  applied_at TIMESTAMP NOT NULL DEFAULT NOW()"
                ")"
            )
        )
        done = {row[0] for row in conn.execute(text("SELECT name FROM schema_migrations"))}

    for name, step in MIGRATIONS:
        if name in done:
            continue
        try:
            with engine.begin() as conn:
                notes = step(conn) or []
                conn.execute(
                    text("INSERT INTO schema_migrations (name) VALUES (:name)"),
                    {"name": name},
                )
        except Exception as exc:  # noqa: BLE001 - deliberately non-fatal, see docstring
            print(f"[schema] migration {name} failed (will retry on next start): {exc}")
            continue
        applied.append(name)
        if notes:
            for note in notes:
                print(f"[schema] migration {name}: {note}")
        else:
            print(f"[schema] migration {name}: nothing to do")

    return applied
