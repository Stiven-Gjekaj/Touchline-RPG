"""Flask application factory for the Touchline RPG web UI.

The routes are a thin layer: each loads the active career, calls one or two
engine functions, and renders a template. All game logic lives in
``touchline.engine``.
"""

from __future__ import annotations

import secrets

from flask import Flask

from touchline.web.active_save import ActiveSave


def create_app() -> Flask:
    """Build and configure the Flask app with a fresh in-memory career slot."""
    app = Flask(__name__)
    # Local single-user app: a per-process key is all flash messaging needs.
    app.secret_key = secrets.token_hex(16)
    app.active_save = ActiveSave()

    from touchline.web.helpers import active_save

    @app.context_processor
    def inject_helpers():  # noqa: D401 - Jinja globals
        return {"active_save": active_save}

    from touchline.web.routes import register_blueprints

    register_blueprints(app)
    return app
