"""Engine/session management. SQLite by default, PostgreSQL via DATABASE_URL."""
from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings
from app.core.logging import log
from app.db.models import Base

connect_args = {}
if settings.database_url.startswith("sqlite"):
    connect_args = {"check_same_thread": False}

engine = create_engine(
    settings.database_url,
    connect_args=connect_args,
    pool_pre_ping=True,
    future=True,
)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _sqlite_pragmas(dbapi_connection, _record):  # pragma: no cover - driver level
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA journal_mode=WAL")
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    # Optional acceleration: native vector column + ANN index when pgvector exists.
    if settings.database_url.startswith("postgresql"):
        from app.db.pgvector import ensure_pgvector

        try:
            ensure_pgvector(engine)
        except Exception as exc:  # noqa: BLE001 - never block startup
            log.warning("pgvector_skipped", extra={"event": "pgvector_skipped", "extra_data": str(exc)[:200]})
    log.info("database_initialised", extra={"event": "init_db"})


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
