"""Save-slot management and new-career creation."""

from __future__ import annotations

import random

from flask import Blueprint, flash, redirect, render_template, request, url_for

from touchline.engine.career import new_career
from touchline.engine.models import Position
from touchline.persistence import save_manager as sm
from touchline.persistence.repositories import IncompatibleSaveError
from touchline.web.helpers import active_save

bp = Blueprint("saves", __name__)


@bp.route("/saves")
def list_saves():
    return render_template("saves.html", saves=sm.list_saves())


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
    slug = sm.create_save(state)
    active_save().set_career(state, rng, slug)
    flash(f"Welcome to {state.user_club.name}! Your career begins.", "success")
    return redirect(url_for("dashboard.home"))


@bp.route("/saves/<slug>/load", methods=["POST"])
def load(slug):
    try:
        state = sm.load_slot(slug)
    except FileNotFoundError:
        flash("That save no longer exists.", "error")
        return redirect(url_for("saves.list_saves"))
    except IncompatibleSaveError:
        flash("That save is from an incompatible version and can't be loaded.", "error")
        return redirect(url_for("saves.list_saves"))
    active_save().set_career(state, random.Random(), slug)
    flash(f"Loaded {state.save_name}.", "success")
    return redirect(url_for("dashboard.home"))


@bp.route("/saves/<slug>/delete", methods=["POST"])
def delete(slug):
    save = active_save()
    sm.delete_slot(slug)
    if save.slug == slug:
        save.clear()
    flash("Save deleted.", "info")
    return redirect(url_for("saves.list_saves"))
