import os

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()  # reads the .env file in the project folder

# On Rumpty: use the internal connection string when the app is deployed
# on Rumpty Cloud itself, or the public one for local dev.
DATABASE_URL_FROM_ENV = bool(os.environ.get("DATABASE_URL"))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/tenura",
)

# A common production misconfiguration: DATABASE_URL is not set, so the app
# silently falls back to localhost (where there is no database) and every
# request that touches the DB fails. Surface it loudly.
if not DATABASE_URL_FROM_ENV:
    print(
        "[config] WARNING: DATABASE_URL is not set - falling back to "
        "localhost:5432. If this is a deployment, set DATABASE_URL to your "
        "Postgres connection string."
    )

# Use the psycopg (v3) driver. Accepts plain postgresql:// URLs too.
if DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)
elif DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
