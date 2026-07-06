"""A single-elimination knockout cup running alongside the league.

A 32-team field is seeded by reputation (the user's club is always included),
drawn randomly, and played down over five rounds on designated league weeks.
Ties are settled on penalties when drawn. The cup is fully separate from the
league's Match/standings machinery, so it never affects the table.
"""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine.models import Cup, CupTie, Honour, MatchPlayerStat
from touchline.engine.rng import weighted_choice
from touchline.engine.simulation import (
    MatchResult,
    _apply_participation_effects,
    goal_share_weight,
    poisson,
    select_starting_xi,
    team_strength,
)
from touchline.engine.state import GameState


def _attribute_goals(xi: list, n_goals: int, rng: random.Random) -> list[int]:
    """Assign each of ``n_goals`` to a scorer in the XI (position-weighted)."""
    if n_goals <= 0 or not xi:
        return []
    weights = {p.id: goal_share_weight(p) for p in xi}
    return [weighted_choice(weights, rng) for _ in range(n_goals)]


def is_cup_week(week: int) -> bool:
    return week in C.CUP_WEEKS


def round_name(round_size: int) -> str:
    return C.CUP_ROUND_NAMES.get(round_size, f"Round of {round_size}")


def _next_cup_week(week: int) -> int | None:
    for candidate in C.CUP_WEEKS:
        if candidate > week:
            return candidate
    return None


def start_cup(state: GameState, rng: random.Random) -> None:
    """Seed the cup field and draw the first round."""
    ranked = sorted(state.clubs.values(), key=lambda c: c.reputation, reverse=True)
    qualifiers = ranked[: C.NUM_CUP_TEAMS]
    if (state.user_club_id is not None
            and all(c.id != state.user_club_id for c in qualifiers)):
        qualifiers[-1] = state.clubs[state.user_club_id]  # guarantee the user a place

    club_ids = [c.id for c in qualifiers]
    rng.shuffle(club_ids)
    state.cup = Cup(name=C.CUP_NAME, round_size=len(club_ids))
    state.cup_ties = []
    _draw_round(state, club_ids, C.CUP_WEEKS[0])


def _draw_round(state: GameState, club_ids: list[int], week: int) -> None:
    size = len(club_ids)
    for i in range(0, size, 2):
        state.cup_ties.append(CupTie(
            id=state.next_id(), round_size=size, week_number=week,
            home_club_id=club_ids[i], away_club_id=club_ids[i + 1],
        ))


def play_cup_week(
    state: GameState, week: int, rng: random.Random
) -> tuple[MatchResult | None, list[str]]:
    """Play this week's cup ties, advance the bracket, and report the user's tie."""
    cup = state.cup
    if cup is None or cup.is_complete:
        return None, []
    ties = [t for t in state.cup_ties if t.week_number == week and not t.is_played]
    if not ties:
        return None, []

    messages: list[str] = []
    user_result: MatchResult | None = None
    winners: list[int] = []
    for tie in ties:
        detailed = state.user_club_id in (tie.home_club_id, tie.away_club_id)
        result = _play_tie(state, tie, rng, detailed)
        winners.append(tie.winner_club_id)
        if detailed:
            user_result = result

    cup.round_size = len(winners)
    if len(winners) == 1:
        cup.champion_club_id = winners[0]
        cup.is_complete = True
        if winners[0] == state.user_club_id:
            state.honours.append(Honour(state.season.number, f"{cup.name} winner"))
            messages.append(f"🏆 You won the {cup.name}!")
        else:
            messages.append(f"{state.clubs[winners[0]].name} won the {cup.name}.")
    else:
        next_week = _next_cup_week(week)
        if next_week is not None:
            _draw_round(state, winners, next_week)
        if user_result is not None:
            if state.user_club_id in winners:
                messages.append(f"You reached the {round_name(len(winners))} of the {cup.name}.")
            else:
                messages.append(f"You were knocked out of the {cup.name}.")
    return user_result, messages


def _play_tie(
    state: GameState, tie: CupTie, rng: random.Random, detailed: bool
) -> MatchResult:
    home = state.clubs[tie.home_club_id]
    away = state.clubs[tie.away_club_id]
    user = state.user_player
    home_is_user = user is not None and user.club_id == home.id
    away_is_user = user is not None and user.club_id == away.id
    tactic = state.tactic
    user_formation = C.FORMATIONS.get(tactic.formation) if tactic else None

    home_xi = select_starting_xi(
        state.squad(home.id), user if home_is_user else None,
        user_formation if home_is_user else None)
    away_xi = select_starting_xi(
        state.squad(away.id), user if away_is_user else None,
        user_formation if away_is_user else None)

    diff = team_strength(home_xi, is_home=True) - team_strength(away_xi, is_home=False)
    home_xg = C.BASE_XG + diff / C.XG_SCALE_FACTOR
    away_xg = C.BASE_XG - diff / C.XG_SCALE_FACTOR
    if (home_is_user or away_is_user) and tactic is not None:
        own_mult, opp_mult = C.MENTALITY_XG[tactic.mentality]
        if home_is_user:
            home_xg *= own_mult
            away_xg *= opp_mult
        else:
            away_xg *= own_mult
            home_xg *= opp_mult
    home_xg = max(home_xg, C.MIN_XG)
    away_xg = max(away_xg, C.MIN_XG)

    home_goals = poisson(home_xg, rng)
    away_goals = poisson(away_xg, rng)
    tie.home_goals = home_goals
    tie.away_goals = away_goals
    tie.is_played = True

    if home_goals > away_goals:
        tie.winner_club_id = home.id
    elif away_goals > home_goals:
        tie.winner_club_id = away.id
    else:
        tie.decided_on_penalties = True
        home_str = team_strength(home_xi, is_home=False)
        away_str = team_strength(away_xi, is_home=False)
        tie.winner_club_id = (home.id if rng.random() < home_str / (home_str + away_str)
                              else away.id)

    _apply_participation_effects(home_xi, home_goals, away_goals, rng)
    _apply_participation_effects(away_xi, away_goals, home_goals, rng)

    result = MatchResult(
        match_id=tie.id, home_club_id=home.id, away_club_id=away.id,
        home_short=home.short_name, away_short=away.short_name,
        home_goals=home_goals, away_goals=away_goals,
    )
    if detailed:
        home_scorers = _attribute_goals(home_xi, home_goals, rng)
        away_scorers = _attribute_goals(away_xi, away_goals, rng)
        lines = [f"{home.name} {home_goals}–{away_goals} {away.name}"]
        for pid in home_scorers:
            lines.append(f"GOAL   {state.players[pid].name} ({home.short_name})")
        for pid in away_scorers:
            lines.append(f"GOAL   {state.players[pid].name} ({away.short_name})")
        if tie.decided_on_penalties:
            lines.append(f"{state.clubs[tie.winner_club_id].name} win on penalties.")
        lines.append(f"[{state.cup.name} · {round_name(tie.round_size)}]")
        result.recap_lines = lines
        if user is not None and (user in home_xi or user in away_xi):
            user_goals = (home_scorers if home_is_user else away_scorers).count(user.id)
            result.user_stat = MatchPlayerStat(
                id=state.next_id(), match_id=tie.id, player_id=user.id,
                goals=user_goals, assists=0, rating=round(6.0 + 0.8 * user_goals, 1),
                minutes_played=90,
            )
    return result
