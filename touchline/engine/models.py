"""Core domain entities as plain dataclasses.

These are pure data objects with no persistence or framework dependencies.
Relationships are expressed by integer id (mirroring the eventual relational
schema) rather than by object reference, so the whole graph serialises cleanly.
Lookups go through :class:`touchline.engine.state.GameState`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

#: The six attributes every player carries (0-99). ``goalkeeping`` is near-zero
#: for outfield players; one uniform schema beats subclassing GK vs outfield.
ATTRIBUTE_NAMES: tuple[str, ...] = (
    "pace",
    "shooting",
    "passing",
    "defending",
    "physical",
    "goalkeeping",
)


class Position(str, Enum):
    """Broad player position, used for squad structure and the match formation."""

    GK = "GK"
    DF = "DF"
    MF = "MF"
    FW = "FW"


class SubPosition(str, Enum):
    """Detailed role within a broad position (display + tactical flavour)."""

    GK = "GK"
    CB = "CB"   # centre-back
    FB = "FB"   # full-back
    DM = "DM"   # defensive midfielder
    CM = "CM"   # central midfielder
    AM = "AM"   # attacking midfielder
    W = "W"     # winger
    ST = "ST"   # striker


class Mentality(str, Enum):
    """Team attacking intent — a risk/reward dial in the match simulation."""

    DEFENSIVE = "DEFENSIVE"
    BALANCED = "BALANCED"
    ATTACKING = "ATTACKING"


class EventType(str, Enum):
    """Kinds of notable moment recorded during a match."""

    GOAL = "GOAL"
    YELLOW_CARD = "YELLOW_CARD"
    RED_CARD = "RED_CARD"
    INJURY = "INJURY"
    KEY_PASS = "KEY_PASS"
    SAVE = "SAVE"


class OfferStatus(str, Enum):
    """State of a transfer offer's negotiation."""

    PENDING_CLUB_DECISION = "PENDING_CLUB_DECISION"
    REJECTED_BY_CLUB = "REJECTED_BY_CLUB"
    PENDING_USER_DECISION = "PENDING_USER_DECISION"
    COMPLETED = "COMPLETED"
    WITHDRAWN = "WITHDRAWN"


class TrainingFocus(str, Enum):
    """A week's training emphasis, chosen by the user (auto-picked for NPCs)."""

    ATTACKING = "ATTACKING"
    PLAYMAKING = "PLAYMAKING"
    DEFENSIVE = "DEFENSIVE"
    PHYSICAL = "PHYSICAL"
    BALANCED = "BALANCED"
    REST = "REST"


@dataclass
class Player:
    """A footballer — the user's character or an NPC squad member/opponent."""

    id: int
    first_name: str
    last_name: str
    age: int
    position: Position
    nationality: str
    club_id: int | None
    pace: int
    shooting: int
    passing: int
    defending: int
    physical: int
    goalkeeping: int
    potential: int
    form: int = 0
    morale: int = 70
    condition: int = 100
    injury_weeks_remaining: int = 0
    is_user: bool = False
    is_retired: bool = False
    contract_id: int | None = None
    sub_position: SubPosition | None = None

    @property
    def name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def role(self) -> str:
        """Detailed role label, falling back to the broad position."""
        return self.sub_position.value if self.sub_position else self.position.value

    @property
    def is_injured(self) -> bool:
        return self.injury_weeks_remaining > 0

    def overall(self) -> int:
        """Position-weighted overall rating (0-99), computed on the fly."""
        # Lazy import avoids a models <-> constants circular import.
        from touchline.engine.constants import POSITION_WEIGHTS

        weights = POSITION_WEIGHTS[self.position]
        return round(sum(getattr(self, attr) * w for attr, w in weights.items()))


@dataclass
class Country:
    """A footballing nation. A single row in v1, modelled so multi-country is
    additive rather than a rewrite."""

    id: int
    name: str


@dataclass
class League:
    """A division within a country's pyramid (tier 1 = top)."""

    id: int
    name: str
    tier: int
    country_id: int
    promotion_slots: int
    relegation_slots: int


@dataclass
class Club:
    """A football club. Its squad is every :class:`Player` with a matching
    ``club_id`` (not a stored list)."""

    id: int
    name: str
    short_name: str
    league_id: int
    division_tier: int
    reputation: int
    wage_budget: int


@dataclass
class Season:
    """The current campaign. Fixtures live as :class:`Match` rows; there is no
    separate fixture entity."""

    id: int
    number: int = 1
    current_week: int = 1
    is_complete: bool = False

    @property
    def year_label(self) -> str:
        return f"Season {self.number}"


@dataclass
class Match:
    """A single fixture. Result fields stay ``None`` until it is played."""

    id: int
    season_id: int
    week_number: int
    home_club_id: int
    away_club_id: int
    home_goals: int | None = None
    away_goals: int | None = None
    is_played: bool = False


@dataclass
class MatchEvent:
    """A notable in-match moment, used to build the recap text."""

    id: int
    match_id: int
    minute: int
    event_type: EventType
    club_id: int
    player_id: int | None
    description: str


@dataclass
class MatchPlayerStat:
    """A player's line in a match. Stored only for the user's player and for
    players involved in a notable event (to feed a cheap top-scorers table)."""

    id: int
    match_id: int
    player_id: int
    goals: int = 0
    assists: int = 0
    rating: float = 6.0
    minutes_played: int = 0
    was_injured: bool = False


@dataclass
class Contract:
    """A player's employment terms at a club."""

    id: int
    player_id: int
    club_id: int
    wage_per_week: int
    signed_on_week: int
    expires_on_week: int


@dataclass
class TransferOffer:
    """A bid for the user's player, tracked through a small state machine."""

    id: int
    player_id: int
    from_club_id: int
    to_club_id: int
    offer_fee: int
    wage_offered: int
    length_offered_years: int
    status: OfferStatus
    week_created: int
    history: list[str] = field(default_factory=list)


@dataclass
class SeasonRecord:
    """A completed season in the user's career (kept after the yearly clear)."""

    season_number: int
    club_name: str
    division_name: str
    appearances: int
    goals: int
    assists: int
    avg_rating: float
    league_position: int | None


@dataclass
class Honour:
    """A trophy or achievement the user earned in a given season."""

    season_number: int
    title: str


@dataclass
class Tactic:
    """The user's chosen setup (NPCs use the default). Formation is a key into
    ``constants.FORMATIONS``."""

    formation: str = "4-4-2"
    mentality: Mentality = Mentality.BALANCED


@dataclass
class Cup:
    """A single-elimination knockout cup running alongside the league."""

    name: str
    round_size: int  # teams remaining in the current round (32, 16, 8, 4, 2, 1)
    champion_club_id: int | None = None
    is_complete: bool = False


@dataclass
class CupTie:
    """One knockout tie. Result fields fill in when it is played; a draw is
    settled on penalties (no replays in v1.1)."""

    id: int
    round_size: int
    week_number: int
    home_club_id: int
    away_club_id: int
    home_goals: int | None = None
    away_goals: int | None = None
    winner_club_id: int | None = None
    is_played: bool = False
    decided_on_penalties: bool = False
