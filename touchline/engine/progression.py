"""Player development: training growth, match-minutes growth, age decline,
retirement, and season-end squad turnover.

All growth/decline is probabilistic and flows through an injected RNG. Young,
high-potential players improve; players past 30 fade, fastest in the legs.
"""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine.models import ATTRIBUTE_NAMES, Player, Position, TrainingFocus
from touchline.engine.rng import clamp
from touchline.engine.state import GameState


# --------------------------------------------------------------------------- #
# Weekly housekeeping
# --------------------------------------------------------------------------- #


def tick_injuries(state: GameState) -> None:
    """Advance injury recovery by one week for every injured player."""
    for player in state.players.values():
        if player.injury_weeks_remaining > 0:
            player.injury_weeks_remaining -= 1


def training_focus_for(player: Player, user_focus: TrainingFocus) -> TrainingFocus:
    """The focus a player trains under (the user's choice, else an NPC default)."""
    if player.is_user:
        return user_focus
    return C.NPC_FOCUS_BY_POSITION[player.position]


def apply_training_week(
    state: GameState, rng: random.Random, user_focus: TrainingFocus
) -> None:
    """Run a non-match week: condition recovery, form decay, and development."""
    for player in state.players.values():
        if player.is_retired:
            continue
        focus = training_focus_for(player, user_focus)
        regen = C.CONDITION_REST_REGEN if focus == TrainingFocus.REST \
            else C.CONDITION_TRAINING_REGEN
        player.condition = int(clamp(player.condition + regen, 0, 100))
        if player.form > 0:
            player.form -= 1
        elif player.form < 0:
            player.form += 1
        # No development while injured or resting.
        if not player.is_injured and focus != TrainingFocus.REST:
            apply_training(player, focus, rng)


# --------------------------------------------------------------------------- #
# Development
# --------------------------------------------------------------------------- #


def _age_factor(age: int) -> float:
    if age <= C.YOUNG_AGE_CEILING:
        return C.YOUNG_AGE_FACTOR
    if age <= 25:
        return C.PRIME_AGE_FACTOR
    return C.FADING_AGE_FACTOR


def apply_training(player: Player, focus: TrainingFocus, rng: random.Random) -> None:
    """Improve a young player's focus attributes toward their potential.

    Players at/after the decline age fade instead. Growth stops once overall
    reaches potential, so the ceiling is respected.
    """
    if player.age >= C.DECLINE_START_AGE:
        apply_decline(player, rng)
        return

    attrs = C.ATTRS_BOOSTED_BY[focus]
    if not attrs:
        return
    age_factor = _age_factor(player.age)
    for attr in attrs:
        headroom = player.potential - player.overall()
        if headroom <= 0:
            break
        chance = clamp(headroom / 100, 0.05, 0.9) * age_factor / len(attrs)
        if rng.random() < chance:
            gain = rng.choice(C.TRAINING_GAIN_CHOICES)
            setattr(player, attr, int(clamp(getattr(player, attr) + gain, 1, 99)))


def apply_match_minutes_growth(player: Player, rng: random.Random) -> None:
    """A small development nudge on the position's key attribute from playing."""
    if player.age >= C.DECLINE_START_AGE:
        return
    headroom = player.potential - player.overall()
    if headroom <= 0:
        return
    chance = clamp(headroom / 100, 0.05, 0.9) * _age_factor(player.age) \
        * C.MATCH_MINUTES_GROWTH_SCALE
    if rng.random() < chance:
        attr = C.PRIMARY_ATTRIBUTE[player.position]
        setattr(player, attr, int(clamp(getattr(player, attr) + 1, 1, 99)))


def apply_decline(player: Player, rng: random.Random) -> None:
    """Erode attributes for a player past the decline age (legs go first)."""
    decline_chance = clamp((player.age - C.DECLINE_START_AGE) * C.DECLINE_PER_YEAR,
                           0.0, C.DECLINE_CHANCE_CAP)
    for attr in ATTRIBUTE_NAMES:
        weight = C.DECLINE_WEIGHTS.get(attr, 1.0)
        if rng.random() < decline_chance * weight:
            loss = rng.choice(C.TRAINING_GAIN_CHOICES)
            setattr(player, attr, int(clamp(getattr(player, attr) - loss, 1, 99)))


# --------------------------------------------------------------------------- #
# Retirement
# --------------------------------------------------------------------------- #


def check_retirement(player: Player, rng: random.Random) -> bool:
    """Whether an NPC retires this off-season (probabilistic, rising with age)."""
    if player.age < C.RETIREMENT_MIN_AGE:
        return False
    if player.age >= C.RETIREMENT_HARD_CAP_AGE:
        return True
    base = clamp((player.age - 32) * 0.12, 0.0, 1.0)
    overall = player.overall()
    if overall >= 70:
        modifier = -0.3
    elif overall < 45:
        modifier = 0.2
    else:
        modifier = 0.0
    return rng.random() < clamp(base + modifier, 0.02, 0.95)


def retire_player(state: GameState, player: Player) -> None:
    """Mark a player retired and release them from their club/contract."""
    player.is_retired = True
    player.club_id = None
    if player.contract_id is not None:
        state.contracts.pop(player.contract_id, None)
        player.contract_id = None


# --------------------------------------------------------------------------- #
# Season-end turnover
# --------------------------------------------------------------------------- #


def process_end_of_season(state: GameState, rng: random.Random) -> list[str]:
    """Retire NPCs and refill thinned squads with youth. Returns log messages."""
    messages: list[str] = []
    for player in list(state.players.values()):
        if player.is_retired or player.is_user:
            continue
        if check_retirement(player, rng):
            retire_player(state, player)
    _replenish_squads(state, rng)
    return messages


def _most_needed_position(squad: list[Player]) -> Position:
    counts = {pos: 0 for pos in Position}
    for player in squad:
        counts[player.position] += 1
    # Largest shortfall against the target composition.
    return max(Position, key=lambda p: C.SQUAD_POSITION_COUNTS[p] - counts[p])


def _replenish_squads(state: GameState, rng: random.Random) -> None:
    from touchline.engine.generation import generate_player  # avoid import cycle

    for club in state.clubs.values():
        squad = state.squad(club.id)
        if len(squad) >= C.MIN_SQUAD_SIZE:
            continue
        tier_target = C.TIER_MEAN_OVERALL[club.division_tier]
        while len(squad) < C.SQUAD_SIZE:
            position = _most_needed_position(squad)
            age = rng.randint(C.YOUTH_INTAKE_AGE_MIN, C.YOUTH_INTAKE_AGE_MAX)
            generate_player(state, position, club, tier_target, rng, age=age)
            squad = state.squad(club.id)


def check_user_status(state: GameState) -> list[str]:
    """Warn the user about decline, or force retirement at the hard floor.

    The user is deliberately never auto-retired by the dice roll NPCs face;
    they keep agency until they choose to retire or hit the floor.
    """
    messages: list[str] = []
    user = state.user_player
    if user is None or user.is_retired:
        return messages
    if user.age >= C.USER_FORCED_RETIRE_AGE and user.overall() < C.USER_FORCED_RETIRE_OVERALL:
        retire_player(state, user)
        messages.append("Your body can no longer keep up — you have retired.")
    elif user.age >= C.USER_DECLINE_WARNING_AGE:
        messages.append(
            "You are past your peak and starting to decline. "
            "You may choose to retire whenever you feel the time is right."
        )
    return messages
