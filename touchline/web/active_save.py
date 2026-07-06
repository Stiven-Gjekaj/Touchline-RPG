"""In-memory holder for the currently loaded career.

For the first web milestone the career lives only in this object (process
restart loses it). The persistence milestone swaps the backing store for
SQLite save files without changing the routes that use this.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from touchline.engine.career import WeekResult
from touchline.engine.state import GameState


@dataclass
class ActiveSave:
    """The career the app currently has open, plus the last week's outcome."""

    state: GameState | None = None
    last_week: WeekResult | None = None
    rng: random.Random = field(default_factory=random.Random)

    @property
    def has_career(self) -> bool:
        return self.state is not None

    def set_career(self, state: GameState, rng: random.Random | None = None) -> None:
        self.state = state
        self.rng = rng or random.Random()
        self.last_week = None

    def clear(self) -> None:
        self.state = None
        self.last_week = None
        self.rng = random.Random()
