import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

_default_db = (Path(__file__).resolve().parent.parent / "birds.db").as_posix()
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{_default_db}")

if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
    )
else:
    engine = create_engine(SQLALCHEMY_DATABASE_URL)

with_autocommit_and_flushing = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)
SessionLocal = with_autocommit_and_flushing
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()