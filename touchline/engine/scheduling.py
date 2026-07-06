"""Fixture scheduling: round-robin generation and season fixture creation."""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine.models import Match
from touchline.engine.state import GameState

Pairing = tuple[int, int]  # (home_index, away_index)


def round_robin_pairings(n_teams: int) -> list[list[Pairing]]:
    """Single round-robin via the circle method.

    Returns ``n_teams - 1`` rounds of ``(home, away)`` index pairs; every team
    meets every other exactly once. The ``round_num`` parity flip stops the
    fixed team from being home in every round.
    """
    if n_teams < 2 or n_teams % 2 != 0:
        raise ValueError("round-robin needs an even team count >= 2")

    teams = list(range(n_teams))
    fixed, rotating = teams[0], teams[1:]
    rounds: list[list[Pairing]] = []
    for round_num in range(n_teams - 1):
        opponent = rotating[-1]
        first: Pairing = (fixed, opponent) if round_num % 2 == 0 else (opponent, fixed)
        pairing: list[Pairing] = [first]
        others = rotating[:-1]
        for i in range(len(others) // 2):
            a, b = others[i], others[-(i + 1)]
            pairing.append((a, b) if round_num % 2 == 0 else (b, a))
        rounds.append(pairing)
        rotating = [rotating[-1]] + rotating[:-1]  # rotate right by one
    return rounds


def double_round_robin(n_teams: int) -> list[list[Pairing]]:
    """Full home-and-away schedule: ``2 * (n_teams - 1)`` rounds."""
    first_half = round_robin_pairings(n_teams)
    second_half = [[(away, home) for home, away in rnd] for rnd in first_half]
    return first_half + second_half


def generate_season_fixtures(state: GameState, rng: random.Random) -> None:
    """Create :class:`Match` rows for every division of the current season.

    All divisions play on the same set of match weeks. Club order is shuffled so
    the pairing/home-away pattern varies season to season.
    """
    for league in state.leagues.values():
        clubs = state.clubs_in_league(league.id)
        rng.shuffle(clubs)
        schedule = double_round_robin(len(clubs))
        for round_idx, pairings in enumerate(schedule):
            week = C.REGULAR_SEASON_START + round_idx
            for home_idx, away_idx in pairings:
                match = Match(
                    id=state.next_id(),
                    season_id=state.season.id,
                    week_number=week,
                    home_club_id=clubs[home_idx].id,
                    away_club_id=clubs[away_idx].id,
                )
                state.matches[match.id] = match
