"""High-level save-slot management: list, create, load, save, and delete.

Each save slot is one ``<slug>.sqlite`` file in the configured save directory.
The slot list is built by scanning that directory and reading each file's meta
row — there is no separate registry to drift out of sync.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

from touchline.config import save_dir
from touchline.engine.constants import SCHEMA_VERSION
from touchline.engine.state import GameState
from touchline.persistence import orm_models as orm
from touchline.persistence.db import make_engine
from touchline.persistence.repositories import load_state, save_state, schema_version


@dataclass
class SaveInfo:
    """Summary of a save slot for the load/manage screens."""

    slug: str
    path: Path
    save_name: str
    created_at: str
    last_played_at: str
    season_number: int
    current_week: int
    player_name: str
    club_name: str
    compatible: bool


def _path_for(slug: str) -> Path:
    return save_dir() / f"{slug}.sqlite"


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-")
    return slug or "career"


def _unique_slug(name: str) -> str:
    existing = {p.stem for p in save_dir().glob("*.sqlite")}
    base = _slugify(name)
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def list_saves() -> list[SaveInfo]:
    """Every save slot found on disk, most recently played first."""
    infos: list[SaveInfo] = []
    for path in save_dir().glob("*.sqlite"):
        info = _read_info(path)
        if info is not None:
            infos.append(info)
    infos.sort(key=lambda i: i.last_played_at, reverse=True)
    return infos


def _read_info(path: Path) -> SaveInfo | None:
    engine = make_engine(path)
    try:
        with Session(engine) as session:
            version = schema_version(session)
            if version is None:
                return None
            if version != SCHEMA_VERSION:
                # Read only always-present columns; the full ORM row may have
                # columns this older file lacks.
                row = session.execute(text(
                    "SELECT save_name, created_at, last_played_at FROM meta WHERE id = 1"
                )).first()
                return SaveInfo(
                    slug=path.stem, path=path,
                    save_name=row[0] if row else path.stem,
                    created_at=row[1] if row else "",
                    last_played_at=row[2] if row else "",
                    season_number=0, current_week=0,
                    player_name="?", club_name="?", compatible=False,
                )

            meta = session.get(orm.MetaRow, 1)
            player = (session.get(orm.PlayerRow, meta.user_player_id)
                      if meta.user_player_id else None)
            club = (session.get(orm.ClubRow, meta.user_club_id)
                    if meta.user_club_id else None)
            season = session.get(orm.SeasonRow, meta.season_id)
            return SaveInfo(
                slug=path.stem, path=path, save_name=meta.save_name,
                created_at=meta.created_at, last_played_at=meta.last_played_at,
                season_number=season.number if season else 0,
                current_week=season.current_week if season else 0,
                player_name=(f"{player.first_name} {player.last_name}"
                             if player else "?"),
                club_name=club.name if club else "?",
                compatible=True,
            )
    finally:
        engine.dispose()


def create_save(state: GameState) -> str:
    """Write a new career to a fresh slot and return its slug."""
    slug = _unique_slug(state.save_name)
    write_slot(slug, state)
    return slug


def write_slot(slug: str, state: GameState) -> None:
    """Persist ``state`` to the given slot (creating the file if needed)."""
    engine = make_engine(_path_for(slug))
    try:
        with Session(engine) as session:
            save_state(session, state)
    finally:
        engine.dispose()


def load_slot(slug: str) -> GameState:
    """Load a career from a slot. Raises if the file is missing."""
    path = _path_for(slug)
    if not path.exists():
        raise FileNotFoundError(f"no save slot named {slug!r}")
    engine = make_engine(path)
    try:
        with Session(engine) as session:
            return load_state(session)
    finally:
        engine.dispose()


def delete_slot(slug: str) -> None:
    """Remove a save slot's file if it exists."""
    path = _path_for(slug)
    if path.exists():
        path.unlink()
