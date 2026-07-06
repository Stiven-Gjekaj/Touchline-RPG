"""League standings and the user's fixture list."""

from __future__ import annotations

from flask import Blueprint, render_template, request

from touchline.engine import constants as C
from touchline.engine.career import compute_standings
from touchline.web.helpers import active_save, require_career

bp = Blueprint("season", __name__)


@bp.route("/standings")
@require_career
def standings():
    state = active_save().state
    default_tier = state.user_club.division_tier
    tier = request.args.get("tier", default=default_tier, type=int)
    tier = min(max(tier, 1), C.NUM_TIERS)
    league = state.league_by_tier(tier)
    return render_template(
        "standings.html",
        state=state,
        league=league,
        table=compute_standings(state, league.id),
        tiers=list(range(1, C.NUM_TIERS + 1)),
        current_tier=tier,
    )


@bp.route("/fixtures")
@require_career
def fixtures():
    state = active_save().state
    club = state.user_club
    matches = [
        m for m in state.matches.values()
        if m.season_id == state.season.id
        and club.id in (m.home_club_id, m.away_club_id)
    ]
    matches.sort(key=lambda m: m.week_number)
    return render_template("fixtures.html", state=state, club=club, matches=matches)
