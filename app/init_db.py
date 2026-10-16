"""
Create/refresh the database schema and seed the clause reference data.

Run manually:  python -m app.init_db
Also runs automatically on app startup (see app/main.py), so a fresh or
previously-uninitialised database always has the tables and seed data it needs
without the operator having to remember a separate step.

`Base.metadata.create_all()` is idempotent: it creates missing tables but never
alters existing ones, so we also add any columns that exist in the models but
are missing from an older database.
"""
from sqlalchemy import inspect, text
from sqlalchemy.schema import CreateColumn

from app.database import engine
from app.models.db import Base


def create_tables() -> None:
    """Create any tables that do not exist yet."""
    Base.metadata.create_all(bind=engine)


def add_missing_columns() -> list[str]:
    """Best-effort: add model columns that are absent from an older database.

    Returns the list of "table.column" names added. Columns that are NOT NULL
    with no default are skipped (adding them to a table that already has rows
    would fail) and reported so the operator can handle them deliberately.
    """
    added: list[str] = []
    inspector = inspect(engine)

    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            continue
        existing = {col["name"] for col in inspector.get_columns(table.name)}
        for column in table.columns:
            if column.name in existing:
                continue
            has_default = (
                column.default is not None
                or column.server_default is not None
                or column.nullable
            )
            if not has_default:
                print(
                    f"[schema] skipped {table.name}.{column.name}: "
                    "NOT NULL with no default; needs a manual migration."
                )
                continue
            ddl = str(CreateColumn(column).compile(dialect=engine.dialect))
            try:
                with engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN {ddl}'))
                added.append(f"{table.name}.{column.name}")
                print(f"[schema] added missing column {table.name}.{column.name}")
            except Exception as exc:  # never let a migration attempt crash startup
                print(f"[schema] could not add {table.name}.{column.name}: {exc}")
    return added


def seed_clause_reference() -> tuple[int, int]:
    """Sync the curated clause_reference rows (upsert by clause_type)."""
    from app.seed_clause_reference import run as seed_run

    return seed_run()


def ensure_schema() -> None:
    """Make the database ready to serve requests."""
    create_tables()
    add_missing_columns()
    added, updated = seed_clause_reference()
    print(f"[schema] clause_reference synced ({added} added, {updated} updated).")


if __name__ == "__main__":
    ensure_schema()
    print("Database ready.")
