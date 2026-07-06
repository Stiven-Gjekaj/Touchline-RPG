"""The season loop: advancing weeks, standings, and end-of-season processing.

``advance_week`` is the single tick the UI drives; it plays fixtures or runs a
training week depending on the calendar, then handles season boundaries
(promotion/relegation and rolling into a fresh campaign).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from touchline.engine import constants as C
from touchline.engine import progression, transfers
from touchline.engine.generation import create_user_player, generate_world
from touchline.engine.models import Club, Position, Season, TrainingFocus
from touchline.engine.scheduling import generate_season_fixtures
from touchline.engine.season_calendar import (
    Phase,
    is_training_week,
    is_window_open,
    phase,
)
from touchline.engine.simulation import MatchResult, simulate_match
from touchline.engine.state import GameState


# --------------------------------------------------------------------------- #
# Standings
# --------------------------------------------------------------------------- #


@dataclass
class StandingRow:
    """A club's line in a division table."""

    club: Club
    played: int = 0
    won: int = 0
    drawn: int = 0
    lost: int = 0
    goals_for: int = 0
    goals_against: int = 0

    @property
    def goal_difference(self) -> int:
        return self.goals_for - self.goals_against

    @property
    def points(self) -> int:
        return self.won * 3 + self.drawn


def compute_standings(state: GameState, league_id: int) -> list[StandingRow]:
    """League table for a division, sorted by points, then GD, then goals for."""
    club_ids = {c.id for c in state.clubs_in_league(league_id)}
    rows = {cid: StandingRow(club=state.clubs[cid]) for cid in club_ids}
    for match in state.matches.values():
        if match.season_id != state.season.id or not match.is_played:
            continue
        if match.home_club_id not in club_ids or match.away_club_id not in club_ids:
            continue
        home = rows[match.home_club_id]
        away = rows[match.away_club_id]
        home.played += 1
        away.played += 1
        home.goals_for += match.home_goals
        home.goals_against += match.away_goals
        away.goals_for += match.away_goals
        away.goals_against += match.home_goals
        if match.home_goals > match.away_goals:
            home.won += 1
            away.lost += 1
        elif match.home_goals < match.away_goals:
            away.won += 1
            home.lost += 1
        else:
            home.drawn += 1
            away.drawn += 1
    return sorted(
        rows.values(),
        key=lambda r: (r.points, r.goal_difference, r.goals_for),
        reverse=True,
    )


def league_position(state: GameState, club_id: int, league_id: int) -> int:
    """1-based finishing position of a club within its division."""
    table = compute_standings(state, league_id)
    for index, row in enumerate(table, start=1):
        if row.club.id == club_id:
            return index
    raise KeyError(f"club {club_id} not in league {league_id}")


# --------------------------------------------------------------------------- #
# Weekly tick
# --------------------------------------------------------------------------- #


@dataclass
class WeekResult:
    """What happened when the player advanced one week."""

    week: int
    phase: Phase
    user_match_result: MatchResult | None = None
    messages: list[str] = field(default_factory=list)
    season_ended: bool = False
    new_season_started: bool = False


def new_career(
    save_name: str,
    first_name: str,
    last_name: str,
    position: Position,
    rng: random.Random,
) -> GameState:
    """Build a fresh world, create the user's player, and schedule season one."""
    state = generate_world(save_name, rng)
    create_user_player(state, first_name, last_name, position, rng)
    generate_season_fixtures(state, rng)
    return state


def advance_week(
    state: GameState,
    rng: random.Random,
    user_focus: TrainingFocus = TrainingFocus.BALANCED,
) -> WeekResult:
    """Advance the game by a single week and return a summary of it."""
    week = state.season.current_week
    current_phase = phase(week)
    result = WeekResult(week=week, phase=current_phase)

    progression.tick_injuries(state)

    if current_phase == Phase.MATCH:
        result.user_match_result = _play_week_matches(state, week, rng)
    elif is_training_week(week):
        progression.apply_training_week(state, rng, user_focus)

    if is_window_open(week):
        result.messages.extend(transfers.roll_transfer_interest(state, rng))

    if week == C.SEASON_END_WEEK:
        _run_end_of_season(state, rng, result)
        result.season_ended = True
        state.season.current_week = C.OFFSEASON_START
    elif week >= C.SEASON_LENGTH:
        _start_new_season(state, rng, result)
    else:
        state.season.current_week += 1

    state.last_played_at = _now()
    return result


def _play_week_matches(
    state: GameState, week: int, rng: random.Random
) -> MatchResult | None:
    """Simulate every fixture in the week; the user's gets full detail."""
    user_result: MatchResult | None = None
    for match in state.matches_in_week(week):
        if match.is_played:
            continue
        is_user_match = state.user_club_id in (match.home_club_id, match.away_club_id)
        outcome = simulate_match(state, match, rng, detailed=is_user_match)
        if is_user_match:
            user_result = outcome
    return user_result


# --------------------------------------------------------------------------- #
# Season boundaries
# --------------------------------------------------------------------------- #


def _run_end_of_season(state: GameState, rng: random.Random, result: WeekResult) -> None:
    user_club = state.user_club
    if user_club is not None:
        position = league_position(state, user_club.id, user_club.league_id)
        league = state.leagues[user_club.league_id]
        result.messages.append(
            f"{state.season.year_label} complete — {user_club.name} finished "
            f"{_ordinal(position)} in {league.name}."
        )

    _apply_promotion_relegation(state, result)

    # Age every active player by a year, then process retirements, youth
    # intake, and the user's decline/forced-retirement status.
    for player in state.players.values():
        if not player.is_retired:
            player.age += 1

    result.messages.extend(progression.process_end_of_season(state, rng))
    result.messages.extend(progression.check_user_status(state))

    state.season.is_complete = True


def retire_user(state: GameState) -> list[str]:
    """Voluntarily retire the user's player (triggered from the UI)."""
    user = state.user_player
    if user is None or user.is_retired:
        return []
    progression.retire_player(state, user)
    return [f"{user.name} has retired from football. What a career."]


def _apply_promotion_relegation(state: GameState, result: WeekResult) -> None:
    """Swap the bottom N of each tier with the top N of the tier below.

    Standings are snapshotted for every division before any club moves, so a
    club relegated into a lower tier can't wrongly appear in that tier's table.
    """
    tables = {
        tier: compute_standings(state, state.league_by_tier(tier).id)
        for tier in range(1, C.NUM_TIERS + 1)
    }
    n = C.PROMOTION_RELEGATION_SLOTS
    user_club_id = state.user_club_id

    for upper_tier in range(1, C.NUM_TIERS):
        lower_tier = upper_tier + 1
        upper_league = state.league_by_tier(upper_tier)
        lower_league = state.league_by_tier(lower_tier)

        relegated = [row.club for row in tables[upper_tier][-n:]]
        promoted = [row.club for row in tables[lower_tier][:n]]

        for club in relegated:
            club.league_id = lower_league.id
            club.division_tier = lower_tier
        for club in promoted:
            club.league_id = upper_league.id
            club.division_tier = upper_tier

        for club in promoted:
            if club.id == user_club_id:
                result.messages.append(f"Promoted! {club.name} go up to {upper_league.name}.")
        for club in relegated:
            if club.id == user_club_id:
                result.messages.append(f"Relegated. {club.name} drop to {lower_league.name}.")


def _start_new_season(state: GameState, rng: random.Random, result: WeekResult) -> None:
    """Roll into a fresh campaign: new season, cleared history, new fixtures."""
    new_season = Season(id=state.next_id(), number=state.season.number + 1, current_week=1)
    # Bound memory: v1 keeps only the current season's matches/events/stats.
    state.matches.clear()
    state.events.clear()
    state.player_stats.clear()
    state.season = new_season
    generate_season_fixtures(state, rng)
    result.new_season_started = True
    result.messages.append(f"A new season begins: {new_season.year_label}.")


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _now() -> str:
    import datetime as _dt

    return _dt.datetime.now().isoformat(timespec="seconds")
