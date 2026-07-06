"""Tests for round-robin scheduling and season fixture generation."""

from __future__ import annotations

import random

import pytest

from touchline.engine import constants as C
from touchline.engine import scheduling
from touchline.engine.career import new_career
from touchline.engine.models import Position


@pytest.mark.parametrize("n_teams", [4, 8, 10, 12, 14])
def test_single_round_robin_each_pair_meets_once(n_teams) -> None:
    rounds = scheduling.round_robin_pairings(n_teams)
    assert len(rounds) == n_teams - 1

    seen: dict[frozenset[int], int] = {}
    for rnd in rounds:
        # No team appears twice in a single round.
        teams_this_round = [t for pair in rnd for t in pair]
        assert len(teams_this_round) == len(set(teams_this_round)) == n_teams
        for home, away in rnd:
            key = frozenset((home, away))
            seen[key] = seen.get(key, 0) + 1

    # Every unordered pair meets exactly once.
    expected_pairs = n_teams * (n_teams - 1) // 2
    assert len(seen) == expected_pairs
    assert all(count == 1 for count in seen.values())


@pytest.mark.parametrize("n_teams", [4, 8, 12])
def test_double_round_robin_home_and_away(n_teams) -> None:
    rounds = scheduling.double_round_robin(n_teams)
    assert len(rounds) == 2 * (n_teams - 1)

    ordered: dict[tuple[int, int], int] = {}
    for rnd in rounds:
        for pair in rnd:
            ordered[pair] = ordered.get(pair, 0) + 1

    # Each ordered (home, away) pairing occurs exactly once...
    assert all(count == 1 for count in ordered.values())
    # ...and its reverse also occurs (home and away swapped).
    for home, away in ordered:
        assert (away, home) in ordered


def test_round_robin_rejects_odd_counts() -> None:
    with pytest.raises(ValueError):
        scheduling.round_robin_pairings(11)


def test_season_fixtures_cover_every_club_evenly() -> None:
    rng = random.Random(3)
    state = new_career("Test", "Sam", "Reed", Position.MF, rng)

    for league in state.leagues.values():
        clubs = state.clubs_in_league(league.id)
        matches = [
            m for m in state.matches.values()
            if state.clubs[m.home_club_id].league_id == league.id
        ]
        # Double round robin: each of N clubs plays 2*(N-1) games.
        expected_games_per_club = 2 * (len(clubs) - 1)
        for club in clubs:
            appearances = sum(
                1 for m in matches
                if club.id in (m.home_club_id, m.away_club_id)
            )
            assert appearances == expected_games_per_club
