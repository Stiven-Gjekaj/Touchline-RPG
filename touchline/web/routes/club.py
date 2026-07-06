"""The user's club: squad view and tactics."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for

from touchline.engine import constants as C
from touchline.engine.career import set_tactic
from touchline.engine.models import Mentality, Position
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


@bp.route("/tactics", methods=["GET"])
@require_career
def tactics():
    state = active_save().state
    return render_template(
        "tactics.html",
        state=state,
        tactic=state.tactic,
        formations=list(C.FORMATIONS.keys()),
        mentalities=list(Mentality),
    )


@bp.route("/tactics", methods=["POST"])
@require_career
def update_tactics():
    save = active_save()
    set_tactic(
        save.state,
        request.form.get("formation", C.DEFAULT_FORMATION),
        request.form.get("mentality", Mentality.BALANCED.value),
    )
    save.persist()
    flash("Tactics updated.", "success")
    return redirect(url_for("club.tactics"))
