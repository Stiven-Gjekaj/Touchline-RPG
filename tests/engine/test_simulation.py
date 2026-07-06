"""Tests for the match-simulation engine."""

from __future__ import annotations

import random
import statistics

from touchline.engine import constants as C
from touchline.engine import generation as gen
from touchline.engine import simulation as sim
from touchline.engine.models import (
    Club,
    Country,
    EventType,
    Match,
    Position,
    Season,
)
from touchline.engine.state import GameState


def _make_state() -> GameState:
    country = Country(id=1, name="Testland")
    season = Season(id=2, number=1, current_week=C.REGULAR_SEASON_START)
    return GameState(save_name="t", created_at="", last_played_at="",
                     schema_version=1, country=country, season=season, _next_id=3)


def _add_club(state: GameState, name: str, target: float, rng: random.Random,
              tier: int = 1) -> Club:
    club = Club(id=state.next_id(), name=name, short_name=name[:3].upper(),
                league_id=1, division_tier=tier, reputation=int(target),
                wage_budget=1000)
    state.clubs[club.id] = club
    for position, count in C.SQUAD_POSITION_COUNTS.items():
        for _ in range(count):
            gen.generate_player(state, position, club, target, rng)
    return club


def _new_match(state: GameState, home: Club, away: Club) -> Match:
    match = Match(id=state.next_id(), season_id=state.season.id,
                  week_number=1, home_club_id=home.id, away_club_id=away.id)
    state.matches[match.id] = match
    return match


def _reset_fitness(state: GameState) -> None:
    for player in state.players.values():
        player.injury_weeks_remaining = 0
        player.condition = 100


# --------------------------------------------------------------------------- #
# Poisson
# --------------------------------------------------------------------------- #


def test_poisson_mean_approximates_lambda() -> None:
    rng = random.Random(0)
    samples = [sim.poisson(1.5, rng) for _ in range(5000)]
    assert abs(statistics.mean(samples) - 1.5) < 0.1
    assert min(samples) >= 0


# --------------------------------------------------------------------------- #
# Determinism / regression
# --------------------------------------------------------------------------- #


def _play_once(seed: int) -> tuple[int, int]:
    state = _make_state()
    rng = random.Random(seed)
    home = _add_club(state, "Alpha", 70, rng)
    away = _add_club(state, "Beta", 60, rng)
    match = _new_match(state, home, away)
    result = sim.simulate_match(state, match, random.Random(seed), detailed=True)
    return result.home_goals, result.away_goals


def test_simulation_is_deterministic_for_a_seed() -> None:
    assert _play_once(2024) == _play_once(2024)


# --------------------------------------------------------------------------- #
# Balance
# --------------------------------------------------------------------------- #


def test_strong_team_usually_beats_weak_team() -> None:
    state = _make_state()
    rng = random.Random(1)
    strong = _add_club(state, "Strong", 85, rng, tier=1)
    weak = _add_club(state, "Weak", 45, rng, tier=3)

    outcome_rng = random.Random(99)
    strong_not_lose = 0
    trials = 1000
    for _ in range(trials):
        _reset_fitness(state)
        match = _new_match(state, strong, weak)
        result = sim.simulate_match(state, match, outcome_rng)
        if result.home_goals >= result.away_goals:
            strong_not_lose += 1
    assert strong_not_lose / trials >= 0.70


# --------------------------------------------------------------------------- #
# Invariants
# --------------------------------------------------------------------------- #


def test_goal_events_reconcile_with_scoreline() -> None:
    state = _make_state()
    rng = random.Random(3)
    home = _add_club(state, "Home", 65, rng)
    away = _add_club(state, "Away", 65, rng)
    outcome_rng = random.Random(5)
    for _ in range(50):
        _reset_fitness(state)
        match = _new_match(state, home, away)
        result = sim.simulate_match(state, match, outcome_rng)
        home_goal_events = sum(
            1 for e in result.events
            if e.event_type == EventType.GOAL and e.club_id == home.id
        )
        away_goal_events = sum(
            1 for e in result.events
            if e.event_type == EventType.GOAL and e.club_id == away.id
        )
        assert home_goal_events == result.home_goals
        assert away_goal_events == result.away_goals


def test_user_rating_within_bounds_and_recorded() -> None:
    state = _make_state()
    rng = random.Random(4)
    home = _add_club(state, "Home", 55, rng)
    away = _add_club(state, "Away", 55, rng)
    # Turn a home player into the user.
    user = state.squad(home.id)[0]
    user.is_user = True
    state.user_player_id = user.id
    state.user_club_id = home.id

    outcome_rng = random.Random(7)
    for _ in range(100):
        _reset_fitness(state)
        match = _new_match(state, home, away)
        result = sim.simulate_match(state, match, outcome_rng, detailed=True)
        assert result.user_stat is not None
        assert 1.0 <= result.user_stat.rating <= 10.0
        assert result.recap_lines  # recap produced for the user's match


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def test_starting_xi_has_eleven_and_respects_injuries() -> None:
    state = _make_state()
    rng = random.Random(6)
    club = _add_club(state, "Club", 60, rng)
    squad = state.squad(club.id)

    xi = sim.select_starting_xi(squad)
    assert len(xi) == sim.STARTING_XI_SIZE

    user = squad[0]
    xi_with_user = sim.select_starting_xi(squad, force_include=user)
    assert user in xi_with_user

    user.injury_weeks_remaining = 3
    xi_injured = sim.select_starting_xi(squad, force_include=user)
    assert user not in xi_injured
    assert len(xi_injured) == sim.STARTING_XI_SIZE
