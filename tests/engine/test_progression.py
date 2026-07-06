"""Tests for development, decline, retirement, and long-run league health."""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine import progression
from touchline.engine.career import advance_week, new_career
from touchline.engine.models import Player, Position, TrainingFocus


def _player(age: int, overall_target: int, potential: int, **overrides) -> Player:
    base = dict(
        id=1, first_name="T", last_name="P", age=age, position=Position.FW,
        nationality="X", club_id=1, pace=overall_target, shooting=overall_target,
        passing=overall_target, defending=overall_target, physical=overall_target,
        goalkeeping=overall_target, potential=potential,
    )
    base.update(overrides)
    return Player(**base)


def test_young_high_potential_player_grows_toward_potential() -> None:
    rng = random.Random(1)
    player = _player(age=18, overall_target=45, potential=80)
    start = player.overall()
    for _ in range(200):
        apply = progression.apply_training(player, TrainingFocus.ATTACKING, rng)  # noqa: F841
    assert player.overall() > start
    # The ceiling is respected (tiny rounding overshoot tolerated).
    assert player.overall() <= player.potential + 1


def test_growth_stops_at_potential() -> None:
    rng = random.Random(2)
    player = _player(age=19, overall_target=60, potential=61)
    for _ in range(500):
        progression.apply_training(player, TrainingFocus.BALANCED, rng)
    assert player.overall() <= player.potential + 1


def test_old_player_declines() -> None:
    rng = random.Random(3)
    player = _player(age=35, overall_target=70, potential=75)
    start = player.overall()
    for _ in range(30):
        progression.apply_decline(player, rng)
    assert player.overall() < start


def test_retirement_probability_is_monotonic_in_age() -> None:
    def retire_rate(age: int) -> float:
        rng = random.Random(age * 7 + 1)
        hits = sum(
            progression.check_retirement(
                _player(age=age, overall_target=55, potential=55), rng
            )
            for _ in range(2000)
        )
        return hits / 2000

    rates = [retire_rate(age) for age in (30, 34, 36, 38, 40)]
    # No one retires before the minimum age; older is never less likely.
    assert rates[0] == 0.0
    assert all(b >= a for a, b in zip(rates, rates[1:]))
    assert rates[-1] > 0.5


def test_user_is_not_auto_retired_but_gets_a_warning() -> None:
    rng = random.Random(4)
    state = new_career("U", "Old", "Timer", Position.MF, rng)
    user = state.user_player
    user.age = 34  # in the decline-warning band
    messages = progression.check_user_status(state)
    assert not user.is_retired
    assert any("decline" in m.lower() for m in messages)


def test_user_forced_retirement_at_floor() -> None:
    rng = random.Random(5)
    state = new_career("U", "Frail", "Legs", Position.MF, rng)
    user = state.user_player
    user.age = 37
    for attr in ("pace", "shooting", "passing", "defending", "physical", "goalkeeping"):
        setattr(user, attr, 25)  # overall well below the floor
    messages = progression.check_user_status(state)
    assert user.is_retired
    assert messages


def test_long_soak_keeps_squads_alive_and_players_turn_over() -> None:
    rng = random.Random(6)
    state = new_career("Marathon", "Long", "Haul", Position.FW, rng)

    seasons = 20
    guard = 0
    max_ticks = seasons * C.SEASON_LENGTH + 50
    while state.season.number <= seasons and guard < max_ticks:
        advance_week(state, rng)
        guard += 1

    # Every club still fields a viable squad after 20 years of turnover.
    for club in state.clubs.values():
        squad = state.squad(club.id)
        assert len(squad) >= C.MIN_SQUAD_SIZE
        # Enough bodies in each outfield group to field a match.
        assert sum(1 for p in squad if p.position == Position.GK) >= 1

    # Retirements actually happened over the run.
    assert any(p.is_retired for p in state.players.values())
    # Divisions are still the right size.
    for tier in range(1, C.NUM_TIERS + 1):
        assert len(state.clubs_in_league(state.league_by_tier(tier).id)) == C.CLUBS_PER_TIER
