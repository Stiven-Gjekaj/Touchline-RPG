"""Shared pytest fixtures.

Engine tests are deliberately plain: they build small domain objects and call
engine functions with a seeded ``random.Random`` so results are deterministic.
No Flask app context or database is required to test the engine.
"""

from __future__ import annotations

import random

import pytest


@pytest.fixture
def rng() -> random.Random:
    """A deterministically seeded RNG for reproducible engine tests."""
    return random.Random(1234)


@pytest.fixture
def save_dir(tmp_path, monkeypatch):
    """Point the app's save directory at a temporary path for the test."""
    monkeypatch.setenv("TOUCHLINE_SAVE_DIR", str(tmp_path))
    return tmp_path
