"""SQLAlchemy database engine and session management."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from archiveinator.config import data_dir as _data_dir

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def db_path() -> Path:
    return _data_dir() / "archiveinator.db"


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _data_dir().mkdir(parents=True, exist_ok=True)
        _engine = create_engine(
            f"sqlite:///{db_path()}",
            connect_args={"check_same_thread": False},
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionFactory
    if _SessionFactory is None:
        _SessionFactory = sessionmaker(bind=get_engine())
    return _SessionFactory


def get_session() -> Iterator[Session]:
    """FastAPI dependency: yields a session with auto-rollback on error."""
    factory = get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
