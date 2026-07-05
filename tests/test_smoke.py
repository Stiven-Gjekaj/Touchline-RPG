"""Smoke tests confirming the package and test harness are wired up."""

from __future__ import annotations

import touchline


def test_package_version_is_exposed() -> None:
    assert touchline.__version__


def test_config_save_dir_honours_override(save_dir) -> None:
    from touchline import config

    assert config.save_dir() == save_dir
    assert save_dir.is_dir()
