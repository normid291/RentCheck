"""Run once: python -m app.init_db"""
from app.database import engine
from app.models.db import Base

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created.")
