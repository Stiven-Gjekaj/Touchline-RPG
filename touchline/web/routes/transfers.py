"""Transfer inbox and negotiation responses."""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, url_for

from touchline.engine.transfers import respond_to_offer
from touchline.web.helpers import active_save, require_career

bp = Blueprint("transfers", __name__)

_ACTIONS = {"accept", "reject", "counter"}


@bp.route("/transfers")
@require_career
def inbox():
    state = active_save().state
    return render_template(
        "transfers.html",
        state=state,
        offers=state.pending_offers_for_user(),
    )


@bp.route("/transfers/<int:offer_id>/<action>", methods=["POST"])
@require_career
def respond(offer_id, action):
    save = active_save()
    if action not in _ACTIONS:
        flash("Unknown response.", "error")
        return redirect(url_for("transfers.inbox"))
    for message in respond_to_offer(save.state, offer_id, action, save.rng):
        flash(message, "info")
    save.persist()
    return redirect(url_for("transfers.inbox"))
