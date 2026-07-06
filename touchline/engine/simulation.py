"""Stat-driven match simulation.

A match produces a scoreline (independent Poisson per side from team strength),
a handful of attributed events (goals, assists, cards, injuries), and — for the
user's match — a personal rating and short text recap. There is no
minute-by-minute play; minutes are cosmetic, assigned only to order the recap.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

from touchline.engine import constants as C
from touchline.engine.models import (
    Club,
    EventType,
    Match,
    MatchEvent,
    MatchPlayerStat,
    Player,
    Position,
)
from touchline.engine.rng import clamp, weighted_choice
from touchline.engine.state import GameState

#: Number of starters per position group (a fixed generic shape; no tactics yet).
FORMATION: dict[Position, int] = {
    Position.GK: 1,
    Position.DF: 4,
    Position.MF: 4,
    Position.FW: 2,
}
STARTING_XI_SIZE = sum(FORMATION.values())  # 11


@dataclass
class MatchResult:
    """The outcome of one simulated match, ready for display."""

    match_id: int
    home_club_id: int
    away_club_id: int
    home_short: str
    away_short: str
    home_goals: int
    away_goals: int
    events: list[MatchEvent] = field(default_factory=list)
    recap_lines: list[str] = field(default_factory=list)
    user_stat: MatchPlayerStat | None = None


# --------------------------------------------------------------------------- #
# Probability helpers
# --------------------------------------------------------------------------- #


def poisson(lam: float, rng: random.Random) -> int:
    """Sample a Poisson-distributed count (Knuth's algorithm)."""
    limit = math.exp(-lam)
    k = 0
    product = 1.0
    while True:
        k += 1
        product *= rng.random()
        if product <= limit:
            return k - 1


def goal_share_weight(player: Player) -> float:
    """Relative likelihood a player is a given goal's scorer."""
    if player.position == Position.FW:
        return player.shooting * 1.0 + player.pace * 0.3
    if player.position == Position.MF:
        return player.shooting * 0.6 + player.passing * 0.3
    if player.position == Position.DF:
        return player.defending * 0.0 + player.shooting * 0.2
    return 0.01  # goalkeeper: essentially never


# --------------------------------------------------------------------------- #
# Selection
# --------------------------------------------------------------------------- #


def select_starting_xi(
    squad: list[Player], force_include: Player | None = None
) -> list[Player]:
    """Pick a starting XI by best overall per position group.

    ``force_include`` (the user's player) is guaranteed a place when fit — a
    deliberate v1 simplification so the user always plays; "earn your place"
    is a candidate for a later version. Short position groups are back-filled
    from the best remaining outfield players rather than failing.
    """
    available = [p for p in squad if not p.is_injured]
    xi: list[Player] = []
    if force_include is not None and not force_include.is_injured:
        xi.append(force_include)

    chosen_ids = {p.id for p in xi}
    by_position: dict[Position, list[Player]] = {pos: [] for pos in Position}
    for player in available:
        if player.id not in chosen_ids:
            by_position[player.position].append(player)
    for players in by_position.values():
        players.sort(key=lambda p: p.overall(), reverse=True)

    # Fill each position group up to its formation count.
    for position, count in FORMATION.items():
        already = sum(1 for p in xi if p.position == position)
        for player in by_position[position][: max(0, count - already)]:
            xi.append(player)
            chosen_ids.add(player.id)

    # Back-fill any shortfall from the best remaining players of any position.
    if len(xi) < STARTING_XI_SIZE:
        remaining = sorted(
            (p for p in available if p.id not in chosen_ids),
            key=lambda p: p.overall(),
            reverse=True,
        )
        for player in remaining[: STARTING_XI_SIZE - len(xi)]:
            xi.append(player)

    return xi[:STARTING_XI_SIZE]


def team_strength(xi: list[Player], *, is_home: bool) -> float:
    """Mean overall of the XI, plus home advantage for the home side."""
    if not xi:
        return C.TIER_MEAN_OVERALL[C.NUM_TIERS]  # degenerate guard
    base = sum(p.overall() for p in xi) / len(xi)
    return base + (C.HOME_ADVANTAGE if is_home else 0.0)


# --------------------------------------------------------------------------- #
# Simulation
# --------------------------------------------------------------------------- #


def simulate_match(
    state: GameState, match: Match, rng: random.Random, *, detailed: bool = False
) -> MatchResult:
    """Simulate ``match``, mutating state (result, events, injuries, form).

    When ``detailed`` (the user's fixture), a personal stat line and full recap
    text are produced; otherwise a cheaper path records only what league tables
    need (scoreline, scorers).
    """
    home = state.clubs[match.home_club_id]
    away = state.clubs[match.away_club_id]
    user = state.user_player
    home_force = user if user is not None and user.club_id == home.id else None
    away_force = user if user is not None and user.club_id == away.id else None

    home_xi = select_starting_xi(state.squad(home.id), home_force)
    away_xi = select_starting_xi(state.squad(away.id), away_force)

    diff = team_strength(home_xi, is_home=True) - team_strength(away_xi, is_home=False)
    home_xg = max(C.BASE_XG + diff / C.XG_SCALE_FACTOR, C.MIN_XG)
    away_xg = max(C.BASE_XG - diff / C.XG_SCALE_FACTOR, C.MIN_XG)
    home_goals = poisson(home_xg, rng)
    away_goals = poisson(away_xg, rng)

    match.home_goals = home_goals
    match.away_goals = away_goals
    match.is_played = True

    # Accumulate per-player goals/assists so stat lines reconcile with the score.
    tallies: dict[int, dict[str, int]] = {}
    events: list[MatchEvent] = []

    def tally(player_id: int, key: str) -> None:
        tallies.setdefault(player_id, {"goals": 0, "assists": 0})[key] += 1

    def add_event(minute, etype, club_id, player_id, description) -> None:
        events.append(MatchEvent(
            id=state.next_id(), match_id=match.id, minute=minute,
            event_type=etype, club_id=club_id, player_id=player_id,
            description=description,
        ))

    _record_goals(home, home_xi, home_goals, rng, tally, add_event)
    _record_goals(away, away_xi, away_goals, rng, tally, add_event)
    injured = _record_discipline_and_injuries(home, home_xi, rng, add_event)
    injured += _record_discipline_and_injuries(away, away_xi, rng, add_event)
    _apply_participation_effects(home_xi, home_goals, away_goals, rng)
    _apply_participation_effects(away_xi, away_goals, home_goals, rng)

    # Stable sort by minute keeps each assist immediately after its goal (they
    # share a minute and the goal is recorded first).
    events.sort(key=lambda e: e.minute)

    # Build the stat lines we keep: everyone involved in an event, plus the user.
    involved_ids = set(tallies) | {p.id for p in injured}
    user_stat: MatchPlayerStat | None = None
    stats: list[MatchPlayerStat] = []
    keep_ids = set(involved_ids)
    if user is not None and (user in home_xi or user in away_xi):
        keep_ids.add(user.id)

    for player_id in keep_ids:
        counts = tallies.get(player_id, {"goals": 0, "assists": 0})
        player = state.players[player_id]
        is_user = player.is_user
        stat = MatchPlayerStat(
            id=state.next_id(),
            match_id=match.id,
            player_id=player_id,
            goals=counts["goals"],
            assists=counts["assists"],
            minutes_played=90,
            was_injured=player in injured,
            rating=6.0,
        )
        if is_user:
            own, opp = (home_goals, away_goals) if user in home_xi else (away_goals, home_goals)
            stat.rating = _personal_rating(counts["goals"], counts["assists"], own, opp, rng)
            user_stat = stat
        stats.append(stat)

    # Persist events and kept stat lines into the world.
    state.events.extend(events)
    state.player_stats.extend(stats)

    result = MatchResult(
        match_id=match.id,
        home_club_id=home.id,
        away_club_id=away.id,
        home_short=home.short_name,
        away_short=away.short_name,
        home_goals=home_goals,
        away_goals=away_goals,
        events=events,
        user_stat=user_stat,
    )
    if detailed:
        result.recap_lines = _build_recap(state, match, home, away, events, user_stat)
    return result


def _record_goals(club, xi, n_goals, rng, tally, add_event) -> None:
    if n_goals <= 0 or not xi:
        return
    scorer_weights = {p.id: goal_share_weight(p) for p in xi}
    passer_lookup = {p.id: p for p in xi}
    for _ in range(n_goals):
        minute = rng.randint(1, 90)
        scorer_id = weighted_choice(scorer_weights, rng)
        tally(scorer_id, "goals")
        scorer = passer_lookup[scorer_id]
        add_event(minute, EventType.GOAL, club.id, scorer_id,
                  f"{scorer.name} scores for {club.short_name}!")
        # Optional assist from a different team-mate, weighted by passing. It
        # shares the goal's minute so it renders right after in the recap.
        assist_weights = {p.id: float(p.passing) for p in xi if p.id != scorer_id}
        if assist_weights and rng.random() < C.ASSIST_PROBABILITY:
            assister_id = weighted_choice(assist_weights, rng)
            tally(assister_id, "assists")
            add_event(minute, EventType.KEY_PASS, club.id, assister_id,
                      f"assisted by {passer_lookup[assister_id].name}")


def _record_discipline_and_injuries(club, xi, rng, add_event) -> list[Player]:
    injured: list[Player] = []
    for player in xi:
        if rng.random() < C.RED_CARD_CHANCE:
            add_event(rng.randint(1, 90), EventType.RED_CARD, club.id, player.id,
                      f"{player.name} ({club.short_name}) is sent off.")
        elif rng.random() < C.YELLOW_CARD_CHANCE:
            add_event(rng.randint(1, 90), EventType.YELLOW_CARD, club.id, player.id,
                      f"{player.name} ({club.short_name}) is booked.")
        # Injury chance falls with physical and condition.
        injury_chance = C.INJURY_BASE_CHANCE * (1.2 - player.physical / 200) \
            * (1.3 - player.condition / 200)
        if rng.random() < injury_chance:
            weeks = _injury_weeks(rng)
            player.injury_weeks_remaining = weeks
            injured.append(player)
            add_event(rng.randint(1, 90), EventType.INJURY, club.id, player.id,
                      f"{player.name} ({club.short_name}) goes off injured "
                      f"(~{weeks} wk).")
    return injured


def _injury_weeks(rng: random.Random) -> int:
    roll = rng.random()
    if roll < 0.65:
        return rng.randint(1, 2)   # minor
    if roll < 0.90:
        return rng.randint(3, 6)   # medium
    return rng.randint(8, 16)      # severe


def _apply_participation_effects(
    xi: list[Player], goals_for: int, goals_against: int, rng: random.Random
) -> None:
    """Condition drop, form nudge, and match-minutes growth for who started."""
    from touchline.engine import progression

    if goals_for > goals_against:
        form_delta = 1
    elif goals_for < goals_against:
        form_delta = -1
    else:
        form_delta = 0
    for player in xi:
        player.condition = int(clamp(player.condition - C.CONDITION_MATCH_DROP, 0, 100))
        player.form = int(clamp(player.form + form_delta, -10, 10))
        progression.apply_match_minutes_growth(player, rng)


def _personal_rating(goals, assists, own_goals, opp_goals, rng) -> float:
    rating = C.RATING_BASE + C.RATING_PER_GOAL * goals + C.RATING_PER_ASSIST * assists
    margin = own_goals - opp_goals
    if margin >= C.BIG_MARGIN:
        rating += C.RATING_RESULT_SWING
    elif margin <= -C.BIG_MARGIN:
        rating -= C.RATING_RESULT_SWING
    rating += rng.gauss(0, C.RATING_NOISE_STD)
    return round(clamp(rating, 1.0, 10.0), 1)


_EVENT_TAGS: dict[EventType, str] = {
    EventType.GOAL: "GOAL",
    EventType.YELLOW_CARD: "YELLOW",
    EventType.RED_CARD: "RED",
    EventType.INJURY: "INJURY",
}


def _build_recap(state, match, home: Club, away: Club, events, user_stat) -> list[str]:
    lines = [f"{home.name} {match.home_goals}–{match.away_goals} {away.name}"]
    for event in events:
        if event.event_type == EventType.KEY_PASS:
            lines.append(f"       ↳ {event.description}")
            continue
        tag = _EVENT_TAGS.get(event.event_type, "")
        lines.append(f"{event.minute:>2}'  {tag:<6} {event.description}")
    if user_stat is not None:
        player = state.players[user_stat.player_id]
        lines.append(
            f"Your match: {player.name} — {user_stat.goals}G "
            f"{user_stat.assists}A, rating {user_stat.rating}/10."
        )
    return lines
