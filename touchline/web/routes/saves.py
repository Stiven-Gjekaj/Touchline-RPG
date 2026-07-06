"""New-career creation. (Save-slot management is added with persistence.)"""

from __future__ import annotations

import random

from flask import Blueprint, flash, redirect, render_template, request, url_for

from touchline.engine.career import new_career
from touchline.engine.models import Position
from touchline.web.helpers import active_save

bp = Blueprint("saves", __name__)


@bp.route("/new", methods=["GET"])
def new_career_form():
    return render_template("new_career.html", positions=list(Position))


@bp.route("/new", methods=["POST"])
def create_career():
    first = (request.form.get("first_name") or "").strip()
    last = (request.form.get("last_name") or "").strip()
    save_name = (request.form.get("save_name") or "").strip() or "My Career"
    position_name = request.form.get("position", Position.MF.value)

    if not first or not last:
        flash("Please enter both a first and last name.", "error")
        return redirect(url_for("saves.new_career_form"))
    try:
        position = Position(position_name)
    except ValueError:
        position = Position.MF

    rng = random.Random()
    state = new_career(save_name, first, last, position, rng)
    active_save().set_career(state, rng)
    flash(f"Welcome to {state.user_club.name}! Your career begins.", "success")
    return redirect(url_for("dashboard.home"))
