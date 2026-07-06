"""Round-trip tests: a saved game reloads field-for-field identical."""

from __future__ import annotations

import random

import pytest
from sqlalchemy.orm import Session

from touchline.engine.career import advance_week, compute_standings, new_career
from touchline.engine.models import Position
from touchline.persistence.db import make_engine
from touchline.persistence.repositories import (
    IncompatibleSaveError,
    load_state,
    save_state,
)


def _seeded_state(seed: int, weeks: int = 10):
    rng = random.Random(seed)
    state = new_career("Round Trip", "Leo", "Silva", Position.FW, rng)
    for _ in range(weeks):
        advance_week(state, rng)
    return state


def _save_then_load(state, tmp_path):
    engine = make_engine(tmp_path / "save.sqlite")
    with Session(engine) as session:
        save_state(session, state)
    with Session(engine) as session:
        return load_state(session)


def test_round_trip_preserves_scalars(tmp_path):
    from touchline.engine.career import set_tactic

    state = _seeded_state(1)
    set_tactic(state, "4-3-3", "ATTACKING")  # exercise non-default tactic
    loaded = _save_then_load(state, tmp_path)
    # Sub-positions survive too (dataclass equality covers the field).
    assert loaded.user_player.sub_position == state.user_player.sub_position

    assert loaded.save_name == state.save_name
    assert loaded.user_player_id == state.user_player_id
    assert loaded.user_club_id == state.user_club_id
    assert loaded._next_id == state._next_id
    assert loaded.season.number == state.season.number
    assert loaded.season.current_week == state.season.current_week
    assert loaded.country == state.country
    assert loaded.tactic == state.tactic


def test_round_trip_preserves_every_entity(tmp_path):
    state = _seeded_state(2)
    loaded = _save_then_load(state, tmp_path)

    # Dataclass equality checks every field.
    assert loaded.players == state.players
    assert loaded.clubs == state.clubs
    assert loaded.leagues == state.leagues
    assert loaded.contracts == state.contracts
    assert loaded.matches == state.matches
    assert {e.id: e for e in loaded.events} == {e.id: e for e in state.events}
    assert ({s.id: s for s in loaded.player_stats}
            == {s.id: s for s in state.player_stats})


def test_round_trip_keeps_standings_identical(tmp_path):
    state = _seeded_state(3, weeks=25)  # a full season of results
    loaded = _save_then_load(state, tmp_path)

    league_id = state.user_club.league_id
    before = {r.club.id: r.points for r in compute_standings(state, league_id)}
    after = {r.club.id: r.points for r in compute_standings(loaded, league_id)}
    assert before == after


def test_loaded_state_is_playable(tmp_path):
    state = _seeded_state(4)
    loaded = _save_then_load(state, tmp_path)
    # Advancing the reloaded game does not blow up and moves the clock on.
    week_before = loaded.season.current_week
    advance_week(loaded, random.Random(0))
    assert loaded.season.current_week != week_before or loaded.season.number > state.season.number


def test_round_trip_preserves_career_history(tmp_path):
    rng = random.Random(9)
    state = new_career("History", "Leo", "Silva", Position.FW, rng)
    for _ in range(28):  # cross a season boundary so a record is written
        advance_week(state, rng)
    assert state.season_records  # sanity: at least one season recorded

    loaded = _save_then_load(state, tmp_path)
    assert loaded.season_records == state.season_records
    assert loaded.honours == state.honours


def test_incompatible_schema_version_raises(tmp_path):
    state = _seeded_state(5, weeks=1)
    engine = make_engine(tmp_path / "save.sqlite")
    with Session(engine) as session:
        save_state(session, state)
    with Session(engine) as session:
        with pytest.raises(IncompatibleSaveError):
            load_state(session, expected_version=999)
