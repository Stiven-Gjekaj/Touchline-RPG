"""The most recent match recap."""

from __future__ import annotations

from flask import Blueprint, render_template

from touchline.web.helpers import active_save, require_career

bp = Blueprint("match", __name__)


@bp.route("/match/last")
@require_career
def last_match():
    save = active_save()
    result = save.last_week.user_match_result if save.last_week else None
    return render_template("match.html", state=save.state, result=result)
