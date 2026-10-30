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

from collections.abc import Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection

from app.database import engine

_FK_ANALYSES_USER = "fk_analyses_user_id_users"
_FK_OTP_USER = "fk_otp_codes_user_id_users"


def _fk_names(conn: Connection, table: str) -> set[str | None]:
    return {fk.get("name") for fk in inspect(conn).get_foreign_keys(table)}


def _index_names(conn: Connection, table: str) -> set[str | None]:
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


def m0002_google_signin(conn: Connection) -> list[str]:
    """Let an account exist without a password, and record its Google identity.

    An account created by signing in with Google has no password to hash, so the
    column has to allow NULL. `add_missing_columns()` adds the new `google_sub`
    column but knows nothing about the unique index that stops two accounts
    claiming one Google identity, so that is created here.
    """
    notes: list[str] = []

    if not _has_table(conn, "users"):
        return notes

    columns = {col["name"]: col for col in inspect(conn).get_columns("users")}

    if "password_hash" in columns and not columns["password_hash"].get("nullable", True):
        conn.execute(
            text("ALTER TABLE users ALTER COLUMN password_hash DROP NOT NULL")
        )
        notes.append("password_hash now allows NULL")

    if "google_sub" not in columns:
        conn.execute(text("ALTER TABLE users ADD COLUMN google_sub VARCHAR(255)"))
        notes.append("added column google_sub")

    if "uq_users_google_sub" not in _index_names(conn, "users"):
        conn.execute(
            text(
                "CREATE UNIQUE INDEX uq_users_google_sub ON users (google_sub)"
            )
        )
        notes.append("added unique index uq_users_google_sub")

    return notes


def m0004_ai_run_events(conn: Connection) -> list[str]:
    """Prepare the private AI-run log and backfill saved analyses once.

    `create_all()` creates the new table; this step adds its indexes explicitly
    (so an existing database and a fresh one agree) and copies historical saved
    analyses into the event log. Guest runs and failed attempts from before this
    table existed cannot be reconstructed, so the backfill covers saved
    analyses only. The event table never receives document or model content.
    """
    notes: list[str] = []

    if not _has_table(conn, "ai_run_events"):
        return notes

    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_ai_run_events_created_at "
            "ON ai_run_events (created_at)"
        )
    )
    conn.execute(
        text(
            "CREATE INDEX IF NOT EXISTS ix_ai_run_events_user_id "
            "ON ai_run_events (user_id)"
        )
    )
    notes.append("ensured ai_run_events indexes")

    # Only backfill an empty event table. It is normally empty on the first boot
    # that adds it; the guard makes a retry harmless.
    has_events = conn.execute(text("SELECT 1 FROM ai_run_events LIMIT 1")).first()
    if has_events is None and _has_table(conn, "analyses") and _has_table(conn, "agreements"):
        conn.execute(
            text(
                "INSERT INTO ai_run_events ("
                "  id, created_at, user_id, is_guest, source, status, "
                "  duration_ms, model_name, input_tokens, output_tokens, error_code"
                ") "
                "SELECT "
                "  gen_random_uuid(), COALESCE(a.created_at, NOW()), a.user_id, "
                "  false, "
                "  CASE WHEN CAST(g.source_type AS TEXT) = 'text' "
                "       THEN 'paste' ELSE 'upload' END, "
                "  'success', NULL, a.model_id, NULL, NULL, NULL "
                "FROM analyses a "
                "JOIN agreements g ON g.id = a.agreement_id"
            )
        )
        notes.append("backfilled saved analyses into ai_run_events")

    return notes


def m0003_clause_provenance(conn: Connection) -> list[str]:
    """Add the constraint/indexes Phase 1 needs.

    The new COLUMNS (jurisdiction, legal_basis, coverage, degraded, ...) are
    added by `add_missing_columns()`, which runs before this step on every boot.
    What it cannot do is create a multi-column unique constraint or a composite
    index, so those live here. Both statements are idempotent.
    """
    notes: list[str] = []

    if _has_table(conn, "clause_reference"):
        conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS "
                "uq_clause_reference_type_juris_version "
                "ON clause_reference (clause_type, jurisdiction, version)"
            )
        )
        notes.append("ensured unique index on clause_reference(type, jurisdiction, version)")

    if _has_table(conn, "analyses"):
        conn.execute(
            text(
                "CREATE INDEX IF NOT EXISTS ix_analyses_user_created "
                "ON analyses (user_id, created_at)"
            )
        )
        notes.append("ensured index analyses(user_id, created_at)")

    return notes


# Order matters: run top to bottom, only the unapplied ones.
MIGRATIONS: list[tuple[str, Callable[[Connection], list[str]]]] = [
    ("0001_user_ownership", m0001_user_ownership),
    ("0002_google_signin", m0002_google_signin),
    ("0003_clause_provenance", m0003_clause_provenance),
    ("0004_ai_run_events", m0004_ai_run_events),
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
