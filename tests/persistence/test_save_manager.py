"""Tests for save-slot management (create/list/load/delete/resume)."""

from __future__ import annotations

import random

from touchline.engine.career import advance_week, new_career
from touchline.engine.models import Position
from touchline.persistence import save_manager as sm


def test_create_list_load_delete(save_dir):
    state = new_career("My Career", "Kai", "Fischer", Position.MF, random.Random(1))
    slug = sm.create_save(state)

    infos = sm.list_saves()
    assert len(infos) == 1
    assert infos[0].player_name == "Kai Fischer"
    assert infos[0].save_name == "My Career"
    assert infos[0].compatible is True

    loaded = sm.load_slot(slug)
    assert loaded.user_player_id == state.user_player_id
    assert loaded.user_player.name == "Kai Fischer"

    sm.delete_slot(slug)
    assert sm.list_saves() == []


def test_two_slots_are_independent(save_dir):
    alpha = new_career("Alpha", "Ada", "One", Position.FW, random.Random(1))
    beta = new_career("Beta", "Bo", "Two", Position.GK, random.Random(2))
    slug_a = sm.create_save(alpha)
    slug_b = sm.create_save(beta)

    assert slug_a != slug_b
    assert len(sm.list_saves()) == 2

    assert sm.load_slot(slug_a).user_player.last_name == "One"
    assert sm.load_slot(slug_b).user_player.last_name == "Two"


def test_resume_after_advancing(save_dir):
    rng = random.Random(3)
    state = new_career("Resume", "Rio", "Vega", Position.MF, rng)
    slug = sm.create_save(state)

    for _ in range(6):
        advance_week(state, rng)
    sm.write_slot(slug, state)
    expected_week = state.season.current_week

    resumed = sm.load_slot(slug)
    assert resumed.season.current_week == expected_week
    assert resumed.user_player.overall() == state.user_player.overall()


def test_incompatible_save_is_listed_but_not_loadable(save_dir):
    import pytest
    from sqlalchemy import text

    from touchline.persistence.db import make_engine
    from touchline.persistence.repositories import IncompatibleSaveError

    state = new_career("Old Save", "A", "B", Position.MF, random.Random(1))
    slug = sm.create_save(state)

    # Tamper the stored version so it looks like a save from another release.
    engine = make_engine(sm._path_for(slug))
    with engine.begin() as conn:
        conn.execute(text("UPDATE meta SET schema_version = 1 WHERE id = 1"))
    engine.dispose()

    infos = sm.list_saves()
    assert len(infos) == 1
    assert infos[0].compatible is False
    with pytest.raises(IncompatibleSaveError):
        sm.load_slot(slug)


def test_slug_collision_gets_suffix(save_dir):
    a = new_career("Same Name", "A", "A", Position.MF, random.Random(1))
    b = new_career("Same Name", "B", "B", Position.MF, random.Random(2))
    slug_a = sm.create_save(a)
    slug_b = sm.create_save(b)
    assert slug_a != slug_b
    assert len(sm.list_saves()) == 2
