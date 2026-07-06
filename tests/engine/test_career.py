"""Tests for the season loop: standings, promotion/relegation, multi-season soak."""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine.career import advance_week, compute_standings, new_career
from touchline.engine.models import Position
from touchline.engine.season_calendar import Phase


def _run_weeks(state, rng, count):
    return [advance_week(state, rng) for _ in range(count)]


def test_full_season_standings_are_consistent() -> None:
    rng = random.Random(21)
    state = new_career("Soak", "Kai", "Fischer", Position.MF, rng)

    # Advance through the whole regular season (up to the season-end week).
    while state.season.current_week < C.SEASON_END_WEEK:
        advance_week(state, rng)

    for league in state.leagues.values():
        clubs = state.clubs_in_league(league.id)
        table = compute_standings(state, league.id)
        n = len(clubs)
        # Everyone played a full double round-robin.
        assert all(row.played == 2 * (n - 1) for row in table)
        assert sum(row.played for row in table) == 2 * n * (n - 1)

        # Points recomputed independently from raw results match the table.
        for row in table:
            wins = draws = 0
            for match in state.matches.values():
                if not match.is_played or match.season_id != state.season.id:
                    continue
                if match.home_club_id == row.club.id:
                    wins += match.home_goals > match.away_goals
                    draws += match.home_goals == match.away_goals
                elif match.away_club_id == row.club.id:
                    wins += match.away_goals > match.home_goals
                    draws += match.away_goals == match.home_goals
            assert row.points == wins * 3 + draws

        # Table is sorted by points, then goal difference, then goals for.
        keys = [(r.points, r.goal_difference, r.goals_for) for r in table]
        assert keys == sorted(keys, reverse=True)


def test_match_weeks_produce_user_results_training_weeks_do_not() -> None:
    rng = random.Random(22)
    state = new_career("Play", "Rio", "Vargas", Position.FW, rng)

    saw_match = saw_training = False
    for _ in range(C.SEASON_END_WEEK - 1):
        result = advance_week(state, rng)
        if result.phase == Phase.MATCH:
            saw_match = True
            assert result.user_match_result is not None
        elif result.phase in (Phase.PRESEASON, Phase.OFFSEASON):
            saw_training = True
            assert result.user_match_result is None
    assert saw_match and saw_training


def test_promotion_relegation_preserves_division_sizes() -> None:
    rng = random.Random(23)
    state = new_career("PromRel", "Nils", "Berg", Position.DF, rng)

    user_club_id = state.user_club_id
    start_tier = state.user_club.division_tier

    # Advance a full 30-week cycle into the next season.
    target_season = state.season.number + 1
    guard = 0
    while state.season.number < target_season and guard < 200:
        advance_week(state, rng)
        guard += 1

    # Each division still has exactly CLUBS_PER_TIER clubs.
    for tier in range(1, C.NUM_TIERS + 1):
        league = state.league_by_tier(tier)
        assert len(state.clubs_in_league(league.id)) == C.CLUBS_PER_TIER

    # The user still owns the same club (its tier may have changed).
    assert state.user_club_id == user_club_id
    assert state.user_club.division_tier in range(1, C.NUM_TIERS + 1)
    _ = start_tier  # tier may or may not have changed depending on results


def test_multi_season_soak_runs_without_error() -> None:
    rng = random.Random(24)
    state = new_career("Marathon", "Theo", "Kane", Position.MF, rng)

    seasons_to_run = 4
    guard = 0
    while state.season.number <= seasons_to_run and guard < 400:
        result = advance_week(state, rng)
        # Week counter always stays within the cycle.
        assert 1 <= state.season.current_week <= C.SEASON_LENGTH
        for message in result.messages:
            assert isinstance(message, str)
        guard += 1

    # Divisions remain intact after several seasons of turnover.
    for tier in range(1, C.NUM_TIERS + 1):
        league = state.league_by_tier(tier)
        assert len(state.clubs_in_league(league.id)) == C.CLUBS_PER_TIER
    # Total club count is unchanged.
    assert len(state.clubs) == C.NUM_TIERS * C.CLUBS_PER_TIER
