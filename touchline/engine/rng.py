"""Small numeric/random helpers.

Every function that needs randomness takes an explicit ``random.Random`` so the
engine is fully deterministic under test.
"""

from __future__ import annotations

import random
from typing import TypeVar

K = TypeVar("K")
Number = TypeVar("Number", int, float)


def clamp(value: Number, low: Number, high: Number) -> Number:
    """Clamp ``value`` into the inclusive ``[low, high]`` range."""
    if value < low:
        return low
    if value > high:
        return high
    return value


def gauss_int(rng: random.Random, mu: float, sigma: float, low: int, high: int) -> int:
    """Draw a Gaussian, round to int, and clamp into ``[low, high]``."""
    return int(clamp(round(rng.gauss(mu, sigma)), low, high))


def weighted_choice(weights: dict[K, float], rng: random.Random) -> K:
    """Return a key chosen with probability proportional to its weight.

    Non-positive total weight falls back to a uniform pick so callers never
    crash on an all-zero weighting (e.g. a squad of pure defenders scoring).
    """
    if not weights:
        raise ValueError("weighted_choice requires at least one option")
    total = sum(max(w, 0.0) for w in weights.values())
    keys = list(weights)
    if total <= 0.0:
        return rng.choice(keys)
    threshold = rng.random() * total
    cumulative = 0.0
    for key in keys:
        cumulative += max(weights[key], 0.0)
        if cumulative >= threshold:
            return key
    return keys[-1]  # floating-point guard
