"""Database engine/session helpers bound to a single save file."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from touchline.persistence.orm_models import Base


def make_engine(path: str | Path) -> Engine:
    """Create an engine for a save file, ensuring its schema exists."""
    engine = create_engine(f"sqlite:///{path}", future=True)
    Base.metadata.create_all(engine)
    return engine


def make_session_factory(path: str | Path) -> sessionmaker[Session]:
    """A sessionmaker bound to the given save file."""
    return sessionmaker(bind=make_engine(path), future=True)
