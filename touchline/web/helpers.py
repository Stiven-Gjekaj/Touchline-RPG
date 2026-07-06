"""Shared helpers for the web layer: state access and small view models."""

from __future__ import annotations

from functools import wraps

from flask import current_app, redirect, url_for

from touchline.engine.models import Match
from touchline.engine.season_calendar import Phase
from touchline.engine.state import GameState

_PHASE_LABELS = {
    Phase.PRESEASON: "Preseason",
    Phase.MATCH: "Match week",
    Phase.SEASON_END: "Season end",
    Phase.OFFSEASON: "Offseason",
}


def active_save():
    """The current :class:`ActiveSave` bound to the running app."""
    return current_app.active_save


def require_career(view):
    """Redirect to the new-career screen if no career is loaded."""

    @wraps(view)
    def wrapped(*args, **kwargs):
        if not active_save().has_career:
            return redirect(url_for("saves.list_saves"))
        return view(*args, **kwargs)

    return wrapped


def phase_label(phase: Phase) -> str:
    return _PHASE_LABELS.get(phase, phase.value.title())


def next_user_fixture(state: GameState) -> Match | None:
    """The user's next unplayed fixture in the current season, if any."""
    if state.user_club_id is None:
        return None
    upcoming = [
        m for m in state.matches.values()
        if m.season_id == state.season.id
        and not m.is_played
        and state.user_club_id in (m.home_club_id, m.away_club_id)
    ]
    upcoming.sort(key=lambda m: m.week_number)
    return upcoming[0] if upcoming else None


def club_name(state: GameState, club_id: int) -> str:
    club = state.clubs.get(club_id)
    return club.name if club else "?"
