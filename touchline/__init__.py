"""Touchline RPG — a text-based football career-mode RPG.

Package layout:
    engine/      Pure domain model + game logic (no Flask/SQLAlchemy/pywebview).
    persistence/ SQLite persistence via SQLAlchemy (the only DB-aware package).
    web/         Thin Flask layer (routes render templates around engine calls).
    desktop/     pywebview launcher wrapping the local Flask server.
    data/        Static word lists for procedural name generation.
"""

__version__ = "0.1.0"
