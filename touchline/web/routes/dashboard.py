"""The home dashboard and the central 'advance week' action."""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, request, url_for

from touchline.engine.career import advance_week
from touchline.engine.models import TrainingFocus
from touchline.engine.season_calendar import is_training_week, is_window_open, phase
from touchline.web.helpers import (
    active_save,
    next_user_fixture,
    phase_label,
    require_career,
)

bp = Blueprint("dashboard", __name__)


def _dashboard_context(save) -> dict:
    """Template context shared by the full page and the htmx partial."""
    state = save.state
    current_phase = phase(state.current_week)
    return dict(
        state=state,
        user=state.user_player,
        club=state.user_club,
        phase=current_phase,
        phase_label=phase_label(current_phase),
        is_training=is_training_week(state.current_week),
        window_open=is_window_open(state.current_week),
        fixture=next_user_fixture(state),
        last_week=save.last_week,
        focuses=list(TrainingFocus),
        pending_offers=len(state.pending_offers_for_user()),
    )


@bp.route("/")
def index():
    if not active_save().has_career:
        return redirect(url_for("saves.list_saves"))
    return redirect(url_for("dashboard.home"))


@bp.route("/dashboard")
@require_career
def home():
    save = active_save()
    user = save.state.user_player
    if user is not None and user.is_retired:
        return render_template(
            "career_over.html", state=save.state, user=user,
            club=save.state.user_club, totals=save.state.career_totals(),
            honours=save.state.honours,
        )
    return render_template("dashboard.html", **_dashboard_context(save))


@bp.route("/advance", methods=["POST"])
@require_career
def advance():
    save = active_save()
    user = save.state.user_player
    if user is not None and user.is_retired:
        return redirect(url_for("dashboard.home"))  # career is over
    focus_name = request.form.get("focus", TrainingFocus.BALANCED.value)
    try:
        focus = TrainingFocus(focus_name)
    except ValueError:
        focus = TrainingFocus.BALANCED
    save.last_week = advance_week(save.state, save.rng, focus)
    save.persist()

    # htmx swaps just the dashboard panel; a plain POST falls back to a reload.
    if request.headers.get("HX-Request"):
        return render_template("partials/dashboard_content.html", **_dashboard_context(save))
    return redirect(url_for("dashboard.home"))
