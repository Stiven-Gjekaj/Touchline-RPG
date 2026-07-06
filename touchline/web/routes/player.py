"""The user player's profile, plus voluntary retirement."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for

from touchline.engine import constants as C
from touchline.engine.career import retire_user
from touchline.engine.models import ATTRIBUTE_NAMES
from touchline.web.helpers import active_save, require_career

bp = Blueprint("player", __name__)


@bp.route("/player")
@require_career
def profile():
    state = active_save().state
    user = state.user_player
    club = state.clubs.get(user.club_id) if user.club_id else None
    stats = [s for s in state.player_stats if s.player_id == user.id]

    appearances = len(stats)
    avg_rating = round(sum(s.rating for s in stats) / appearances, 2) if appearances else "—"
    summary = {
        "appearances": appearances,
        "goals": sum(s.goals for s in stats),
        "assists": sum(s.assists for s in stats),
        "avg_rating": avg_rating,
    }
    can_retire = user.age >= C.USER_DECLINE_WARNING_AGE and not user.is_retired
    return render_template(
        "player.html",
        state=state,
        user=user,
        club=club,
        contract=state.contract_for(user.id),
        summary=summary,
        attribute_names=ATTRIBUTE_NAMES,
        can_retire=can_retire,
    )


@bp.route("/history")
@require_career
def history():
    state = active_save().state
    return render_template(
        "history.html",
        state=state,
        user=state.user_player,
        records=list(reversed(state.season_records)),
        honours=list(reversed(state.honours)),
        totals=state.career_totals(),
    )


@bp.route("/player/retire", methods=["POST"])
@require_career
def retire():
    save = active_save()
    for message in retire_user(save.state):
        flash(message, "info")
    save.persist()
    return redirect(url_for("dashboard.home"))
