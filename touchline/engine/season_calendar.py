"""The season calendar: which phase a week is in and when windows are open.

Named ``season_calendar`` to avoid shadowing the standard-library ``calendar``.
The 30-week cycle is: preseason (1-3), matches (4-25), season end (26),
offseason (27-30).
"""

from __future__ import annotations

from enum import Enum

from touchline.engine import constants as C


class Phase(str, Enum):
    PRESEASON = "PRESEASON"
    MATCH = "MATCH"
    SEASON_END = "SEASON_END"
    OFFSEASON = "OFFSEASON"


def phase(week: int) -> Phase:
    """Return the calendar phase for a 1-based week number."""
    if week <= C.PRESEASON_END:
        return Phase.PRESEASON
    if week <= C.REGULAR_SEASON_END:
        return Phase.MATCH
    if week == C.SEASON_END_WEEK:
        return Phase.SEASON_END
    return Phase.OFFSEASON


def is_match_week(week: int) -> bool:
    return C.REGULAR_SEASON_START <= week <= C.REGULAR_SEASON_END


def is_training_week(week: int) -> bool:
    return phase(week) in (Phase.PRESEASON, Phase.OFFSEASON)


def is_window_open(week: int) -> bool:
    """Transfer window: open in preseason (1-3) and offseason (27-30)."""
    return week <= C.PRESEASON_END or week >= C.OFFSEASON_START


def match_number(week: int) -> int | None:
    """1-based match-week ordinal (1..22), or ``None`` outside the season."""
    if not is_match_week(week):
        return None
    return week - C.REGULAR_SEASON_START + 1
