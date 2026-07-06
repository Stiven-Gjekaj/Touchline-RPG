"""Weekly player upkeep: injury recovery, condition, and form.

Attribute growth, age decline, and retirement are layered on in a later
milestone; this module owns the per-week housekeeping the season loop needs.
"""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine.models import TrainingFocus
from touchline.engine.rng import clamp
from touchline.engine.state import GameState


def tick_injuries(state: GameState) -> None:
    """Advance injury recovery by one week for every injured player."""
    for player in state.players.values():
        if player.injury_weeks_remaining > 0:
            player.injury_weeks_remaining -= 1


def training_focus_for(player, user_focus: TrainingFocus) -> TrainingFocus:
    """The focus a player trains under this week (user's choice, else NPC default)."""
    if player.is_user:
        return user_focus
    return C.NPC_FOCUS_BY_POSITION[player.position]


def apply_training_week(
    state: GameState, rng: random.Random, user_focus: TrainingFocus
) -> None:
    """Run a non-match week: condition recovery and gentle form decay.

    (Attribute growth/decline is added in the progression milestone.)
    """
    for player in state.players.values():
        if player.is_retired:
            continue
        focus = training_focus_for(player, user_focus)
        regen = C.CONDITION_REST_REGEN if focus == TrainingFocus.REST \
            else C.CONDITION_TRAINING_REGEN
        player.condition = int(clamp(player.condition + regen, 0, 100))
        # Form drifts back toward neutral between matches.
        if player.form > 0:
            player.form -= 1
        elif player.form < 0:
            player.form += 1
