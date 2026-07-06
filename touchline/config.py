"""Application configuration: save-directory resolution and global constants.

The save directory is resolved once here so the rest of the app never computes
paths relative to ``__file__`` or the current working directory — that would
break under a PyInstaller bundle (which extracts to a temp dir each run). Tests
override the location via the ``TOUCHLINE_SAVE_DIR`` environment variable.
"""

from __future__ import annotations

import os
from pathlib import Path

from platformdirs import user_data_dir

from touchline.engine.constants import SCHEMA_VERSION  # noqa: F401  (re-exported)

APP_NAME = "TouchlineRPG"
APP_AUTHOR = "Touchline"

_SAVE_DIR_ENV = "TOUCHLINE_SAVE_DIR"


def save_dir() -> Path:
    """Return the directory that holds save-slot ``.sqlite`` files.

    Honours the ``TOUCHLINE_SAVE_DIR`` environment variable (used by tests and
    power users); otherwise falls back to the per-user data directory. The
    directory is created if it does not yet exist.
    """
    override = os.environ.get(_SAVE_DIR_ENV)
    path = Path(override) if override else Path(user_data_dir(APP_NAME, APP_AUTHOR)) / "saves"
    path.mkdir(parents=True, exist_ok=True)
    return path
