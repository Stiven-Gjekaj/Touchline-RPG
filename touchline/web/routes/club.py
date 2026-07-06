"""The user's club squad view."""

from __future__ import annotations

from flask import Blueprint, render_template

from touchline.engine.models import Position
from touchline.web.helpers import active_save, require_career

bp = Blueprint("club", __name__)

_POSITION_ORDER = {Position.GK: 0, Position.DF: 1, Position.MF: 2, Position.FW: 3}


@bp.route("/squad")
@require_career
def squad():
    state = active_save().state
    club = state.user_club
    players = sorted(
        state.squad(club.id),
        key=lambda p: (_POSITION_ORDER[p.position], -p.overall()),
    )
    return render_template(
        "squad.html",
        state=state,
        club=club,
        players=players,
        user_id=state.user_player_id,
    )
