"""Procedural generation of the world: leagues, clubs, players, and names.

The generated world is one fictional country with a 3-tier, 12-clubs-per-tier
pyramid (~720 players). Top-tier squads are stronger on average than lower tiers.
"""

from __future__ import annotations

import datetime as _dt
import json
import random
from importlib import resources

from touchline.engine import constants as C
from touchline.engine.models import (
    Club,
    Contract,
    Country,
    League,
    Player,
    Position,
    Season,
)
from touchline.engine.rng import clamp
from touchline.engine.state import GameState

# --------------------------------------------------------------------------- #
# Static data (loaded once)
# --------------------------------------------------------------------------- #


def _load_json(filename: str):
    with resources.files("touchline.data").joinpath(filename).open(encoding="utf-8") as fh:
        return json.load(fh)


_FIRST_NAMES: list[str] = _load_json("first_names.json")
_LAST_NAMES: list[str] = _load_json("last_names.json")
_CLUB_PARTS: dict[str, list[str]] = _load_json("club_name_parts.json")


# --------------------------------------------------------------------------- #
# Names
# --------------------------------------------------------------------------- #


def generate_person_name(rng: random.Random) -> tuple[str, str]:
    """Return a ``(first, last)`` name pair."""
    return rng.choice(_FIRST_NAMES), rng.choice(_LAST_NAMES)


def generate_club_name(rng: random.Random, used: set[str]) -> str:
    """Return a club name unique within ``used`` (which is updated in place)."""
    for _ in range(1000):
        place = rng.choice(_CLUB_PARTS["prefixes"]) + rng.choice(_CLUB_PARTS["suffixes"])
        suffix = rng.choice(_CLUB_PARTS["club_suffixes"])
        name = f"{place} {suffix}"
        if name not in used:
            used.add(name)
            return name
    raise RuntimeError("exhausted club-name combinations")  # pragma: no cover


def _short_code(name: str, used: set[str]) -> str:
    """Derive a unique 3-letter uppercase code from a club name."""
    letters = [ch for ch in name.upper() if ch.isalpha()]
    base = "".join(letters[:3]) if len(letters) >= 3 else (name.upper() + "XXX")[:3]
    if base not in used:
        used.add(base)
        return base
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        candidate = base[:2] + ch
        if candidate not in used:
            used.add(candidate)
            return candidate
    raise RuntimeError("exhausted short codes")  # pragma: no cover


# --------------------------------------------------------------------------- #
# Attributes / potential
# --------------------------------------------------------------------------- #


def generate_attributes(
    position: Position, target_overall: float, rng: random.Random
) -> dict[str, int]:
    """Generate the six attributes for a player of ``position``.

    Attributes are skewed toward the ones the position values, but the skew is
    re-centred so the resulting :meth:`Player.overall` stays close to
    ``target_overall`` (a naive skew would systematically inflate overalls, most
    of all for specialised positions like GK).
    """
    weights = C.POSITION_WEIGHTS[position]
    avg_weight = sum(weights.values()) / len(weights)
    # Weighted contribution of the raw skew; subtract it so overall ~= target.
    bias = 100.0 * (sum(w * w for w in weights.values()) - avg_weight)
    base = target_overall - bias

    attrs: dict[str, int] = {}
    for attr, weight in weights.items():
        skew = (weight - avg_weight) * 100.0
        raw = base + skew + rng.gauss(0, C.ATTRIBUTE_JITTER_STD)
        attrs[attr] = int(clamp(round(raw), 1, 99))
    return attrs


def generate_potential(age: int, current_overall: int, rng: random.Random) -> int:
    """Growth ceiling for a player: generous for the young, ~flat for veterans."""
    if age < C.YOUNG_AGE_CEILING:
        bonus = rng.randint(C.YOUNG_POTENTIAL_MIN_BONUS, C.YOUNG_POTENTIAL_MAX_BONUS)
    elif age >= C.VETERAN_AGE_FLOOR:
        bonus = rng.randint(0, 3)
    else:
        bonus = rng.randint(2, 12)
    return int(clamp(current_overall + bonus, current_overall, 99))


# --------------------------------------------------------------------------- #
# Players
# --------------------------------------------------------------------------- #


def _wage_for(overall: int, tier: int) -> int:
    """A simple wage figure bounded by club quality (not a full economy)."""
    tier_scale = (C.NUM_TIERS - tier) + 1  # tier 1 -> 3, tier 3 -> 1
    return max(50, int((overall ** 2) / 20 * tier_scale))


def _make_contract(
    state: GameState, player: Player, club: Club, rng: random.Random
) -> Contract:
    years = rng.randint(1, 4)
    contract = Contract(
        id=state.next_id(),
        player_id=player.id,
        club_id=club.id,
        wage_per_week=_wage_for(player.overall(), club.division_tier),
        signed_on_week=state.current_week,
        expires_on_week=state.current_week + years * C.SEASON_LENGTH,
    )
    state.contracts[contract.id] = contract
    player.contract_id = contract.id
    return contract


def generate_player(
    state: GameState,
    position: Position,
    club: Club | None,
    target_overall: float,
    rng: random.Random,
    *,
    age: int | None = None,
    is_user: bool = False,
    sub_position=None,
) -> Player:
    """Create, register, and return a player (with a contract if it has a club)."""
    if age is None:
        age = int(clamp(round(rng.gauss(C.PLAYER_AGE_MEAN, C.PLAYER_AGE_STD)),
                        C.PLAYER_AGE_MIN, C.PLAYER_AGE_MAX))
    first, last = generate_person_name(rng)
    attrs = generate_attributes(position, target_overall, rng)
    player = Player(
        id=state.next_id(),
        first_name=first,
        last_name=last,
        age=age,
        position=position,
        nationality=state.country.name,
        club_id=club.id if club else None,
        potential=0,  # set below once overall is known
        is_user=is_user,
        condition=100,
        morale=70,
        sub_position=sub_position or rng.choice(C.SUB_POSITIONS_BY_BROAD[position]),
        **attrs,
    )
    player.potential = generate_potential(age, player.overall(), rng)
    state.players[player.id] = player
    if club is not None:
        _make_contract(state, player, club, rng)
    return player


def _generate_squad(
    state: GameState, club: Club, tier_target: float, rng: random.Random
) -> None:
    for position, count in C.SQUAD_POSITION_COUNTS.items():
        for _ in range(count):
            generate_player(state, position, club, tier_target, rng)


# --------------------------------------------------------------------------- #
# Clubs / leagues / world
# --------------------------------------------------------------------------- #


def _generate_club(
    state: GameState,
    league: League,
    used_names: set[str],
    used_codes: set[str],
    rng: random.Random,
) -> Club:
    tier_mean = C.TIER_MEAN_OVERALL[league.tier]
    club_offset = clamp(rng.gauss(0, C.CLUB_OFFSET_STD),
                        -C.CLUB_OFFSET_CLAMP, C.CLUB_OFFSET_CLAMP)
    reputation = int(clamp(round(tier_mean + club_offset + rng.gauss(0, 3)), 1, 99))
    name = generate_club_name(rng, used_names)
    club = Club(
        id=state.next_id(),
        name=name,
        short_name=_short_code(name, used_codes),
        league_id=league.id,
        division_tier=league.tier,
        reputation=reputation,
        wage_budget=reputation * 1000,
        balance=reputation * C.CLUB_BALANCE_PER_REP,
    )
    state.clubs[club.id] = club
    _generate_squad(state, club, tier_mean + club_offset, rng)
    return club


def _generate_league(state: GameState, tier: int, rng: random.Random) -> League:
    names = {1: "Premier Division", 2: "Championship", 3: "League One"}
    league = League(
        id=state.next_id(),
        name=names.get(tier, f"Tier {tier}"),
        tier=tier,
        country_id=state.country.id,
        promotion_slots=0 if tier == 1 else C.PROMOTION_RELEGATION_SLOTS,
        relegation_slots=0 if tier == C.NUM_TIERS else C.PROMOTION_RELEGATION_SLOTS,
    )
    state.leagues[league.id] = league
    return league


def generate_world(save_name: str, rng: random.Random) -> GameState:
    """Build a complete fresh world and return its :class:`GameState`."""
    now = _dt.datetime.now().isoformat(timespec="seconds")
    country = Country(id=1, name="Albion")
    season = Season(id=2, number=1, current_week=1)
    state = GameState(
        save_name=save_name,
        created_at=now,
        last_played_at=now,
        schema_version=C.SCHEMA_VERSION,
        country=country,
        season=season,
        _next_id=3,  # ids 1 and 2 taken by country and season
    )
    state.country = country

    used_names: set[str] = set()
    used_codes: set[str] = set()
    for tier in range(1, C.NUM_TIERS + 1):
        league = _generate_league(state, tier, rng)
        for _ in range(C.CLUBS_PER_TIER):
            _generate_club(state, league, used_names, used_codes, rng)
    return state


def create_user_player(
    state: GameState,
    first_name: str,
    last_name: str,
    position: Position,
    rng: random.Random,
) -> Player:
    """Create the user's player and slot them into a bottom-tier club."""
    bottom_league = state.league_by_tier(C.NUM_TIERS)
    club = rng.choice(state.clubs_in_league(bottom_league.id))

    age = rng.randint(C.USER_START_AGE_MIN, C.USER_START_AGE_MAX)
    target = rng.uniform(C.USER_START_OVERALL_MIN, C.USER_START_OVERALL_MAX)
    attrs = generate_attributes(position, target, rng)

    player = Player(
        id=state.next_id(),
        first_name=first_name,
        last_name=last_name,
        age=age,
        position=position,
        nationality=state.country.name,
        club_id=club.id,
        potential=0,
        is_user=True,
        sub_position=rng.choice(C.SUB_POSITIONS_BY_BROAD[position]),
        **attrs,
    )
    # The user gets extra-generous headroom for a rags-to-riches arc.
    player.potential = int(clamp(player.overall() + rng.randint(20, 40),
                                 player.overall(), 99))
    state.players[player.id] = player
    _make_contract(state, player, club, rng)

    state.user_player_id = player.id
    state.user_club_id = club.id
    return player
