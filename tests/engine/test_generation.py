"""Tests for procedural world generation and the overall() rating."""

from __future__ import annotations

import random
import statistics

import pytest

from touchline.engine import constants as C
from touchline.engine import generation as gen
from touchline.engine.models import Player, Position


def _player(**overrides) -> Player:
    base = dict(
        id=1, first_name="Test", last_name="Player", age=20, position=Position.MF,
        nationality="Albion", club_id=None, pace=50, shooting=50, passing=50,
        defending=50, physical=50, goalkeeping=50, potential=50,
    )
    base.update(overrides)
    return Player(**base)


def test_overall_of_flat_fifty_is_fifty() -> None:
    # Each weight row sums to 1.0, so an all-50 player is exactly 50 anywhere.
    for position in Position:
        assert _player(position=position).overall() == 50


def test_overall_rewards_position_relevant_attributes() -> None:
    striker = _player(position=Position.FW, shooting=90, defending=20)
    defender = _player(position=Position.DF, shooting=90, defending=20)
    # The striker's shooting matters far more than the defender's does.
    assert striker.overall() > defender.overall()


@pytest.mark.parametrize("seed", range(5))
@pytest.mark.parametrize("position", list(Position))
@pytest.mark.parametrize("target", [35, 55, 75])
def test_generated_overall_tracks_target(position, target, seed) -> None:
    rng = random.Random(seed)
    overalls = [
        Player(id=1, first_name="A", last_name="B", age=24, position=position,
               nationality="X", club_id=None, potential=99,
               **gen.generate_attributes(position, target, rng)).overall()
        for _ in range(60)
    ]
    # Re-centring keeps the mean generated overall close to the requested target.
    assert abs(statistics.mean(overalls) - target) < 4


def test_world_has_expected_structure() -> None:
    state = gen.generate_world("Test Save", random.Random(7))
    assert len(state.leagues) == C.NUM_TIERS
    assert len(state.clubs) == C.NUM_TIERS * C.CLUBS_PER_TIER
    for club in state.clubs.values():
        assert len(state.squad(club.id)) == C.SQUAD_SIZE
    # ~720 players total (36 clubs x 20).
    assert len(state.players) == C.NUM_TIERS * C.CLUBS_PER_TIER * C.SQUAD_SIZE


def test_squad_position_counts_match_config() -> None:
    state = gen.generate_world("Test Save", random.Random(8))
    club = next(iter(state.clubs.values()))
    squad = state.squad(club.id)
    for position, expected in C.SQUAD_POSITION_COUNTS.items():
        assert sum(1 for p in squad if p.position == position) == expected


def test_tier_strength_is_ordered() -> None:
    state = gen.generate_world("Test Save", random.Random(9))

    def tier_mean(tier: int) -> float:
        league = state.league_by_tier(tier)
        players = [p for club in state.clubs_in_league(league.id)
                   for p in state.squad(club.id)]
        return statistics.mean(p.overall() for p in players)

    assert tier_mean(1) > tier_mean(2) > tier_mean(3)


def test_club_names_and_codes_are_unique() -> None:
    state = gen.generate_world("Test Save", random.Random(10))
    names = [c.name for c in state.clubs.values()]
    codes = [c.short_name for c in state.clubs.values()]
    assert len(names) == len(set(names))
    assert len(codes) == len(set(codes))
    assert all(len(code) == 3 for code in codes)


def test_every_player_has_a_contract() -> None:
    state = gen.generate_world("Test Save", random.Random(11))
    for player in state.players.values():
        contract = state.contract_for(player.id)
        assert contract is not None
        assert contract.club_id == player.club_id
        assert contract.expires_on_week > state.current_week


def test_create_user_player_places_young_prospect_in_bottom_tier() -> None:
    rng = random.Random(12)
    state = gen.generate_world("Test Save", rng)
    player = gen.create_user_player(state, "Ada", "Stone", Position.FW, rng)

    assert player.is_user is True
    assert state.user_player_id == player.id
    assert state.user_club_id == player.club_id
    assert C.USER_START_AGE_MIN <= player.age <= C.USER_START_AGE_MAX
    assert player.potential > player.overall()
    # Placed in a bottom-tier club.
    assert state.clubs[player.club_id].division_tier == C.NUM_TIERS
    assert state.contract_for(player.id) is not None
