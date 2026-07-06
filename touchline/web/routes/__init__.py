"""Blueprint registration for the web UI."""

from __future__ import annotations

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from touchline.web.routes import club, dashboard, match, player, saves, season

    app.register_blueprint(dashboard.bp)
    app.register_blueprint(saves.bp)
    app.register_blueprint(season.bp)
    app.register_blueprint(club.bp)
    app.register_blueprint(player.bp)
    app.register_blueprint(match.bp)
