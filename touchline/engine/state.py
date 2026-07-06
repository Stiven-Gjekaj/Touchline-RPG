"""The aggregate game state — the whole world for one save slot.

Holds every entity keyed by id and offers the lookups the rest of the engine and
the web layer need. This is the object the in-memory prototype keeps in RAM and
that the persistence layer round-trips to SQLite.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from touchline.engine.models import (
    Club,
    Contract,
    Country,
    Honour,
    League,
    Match,
    MatchEvent,
    MatchPlayerStat,
    Player,
    Season,
    SeasonRecord,
    Tactic,
    TransferOffer,
)


@dataclass
class GameState:
    """Everything that makes up a single career/save."""

    save_name: str
    created_at: str
    last_played_at: str
    schema_version: int
    country: Country
    season: Season
    user_player_id: int | None = None
    user_club_id: int | None = None

    leagues: dict[int, League] = field(default_factory=dict)
    clubs: dict[int, Club] = field(default_factory=dict)
    players: dict[int, Player] = field(default_factory=dict)
    matches: dict[int, Match] = field(default_factory=dict)
    contracts: dict[int, Contract] = field(default_factory=dict)
    transfer_offers: dict[int, TransferOffer] = field(default_factory=dict)
    events: list[MatchEvent] = field(default_factory=list)
    player_stats: list[MatchPlayerStat] = field(default_factory=list)

    # Career history for the user's player (survives the yearly data clear).
    season_records: list[SeasonRecord] = field(default_factory=list)
    honours: list[Honour] = field(default_factory=list)

    # The user's chosen tactic (NPCs use the default formation/mentality).
    tactic: Tactic = field(default_factory=Tactic)

    _next_id: int = 1

    # -- id allocation ----------------------------------------------------- #

    def next_id(self) -> int:
        """Return a fresh, monotonically increasing entity id."""
        value = self._next_id
        self._next_id += 1
        return value

    def sync_next_id(self) -> None:
        """Recompute the id counter from existing entities (used after load)."""
        used = [0]
        for collection in (self.leagues, self.clubs, self.players, self.matches,
                           self.contracts, self.transfer_offers):
            used.extend(collection)
        used.extend(e.id for e in self.events)
        used.extend(s.id for s in self.player_stats)
        self._next_id = max(used) + 1

    # -- convenience accessors -------------------------------------------- #

    @property
    def current_week(self) -> int:
        return self.season.current_week

    @property
    def user_player(self) -> Player | None:
        if self.user_player_id is None:
            return None
        return self.players.get(self.user_player_id)

    @property
    def user_club(self) -> Club | None:
        if self.user_club_id is None:
            return None
        return self.clubs.get(self.user_club_id)

    # -- queries ----------------------------------------------------------- #

    def squad(self, club_id: int) -> list[Player]:
        """Active (non-retired) players contracted to a club."""
        return [
            p for p in self.players.values()
            if p.club_id == club_id and not p.is_retired
        ]

    def clubs_in_league(self, league_id: int) -> list[Club]:
        return [c for c in self.clubs.values() if c.league_id == league_id]

    def league_by_tier(self, tier: int) -> League:
        for league in self.leagues.values():
            if league.tier == tier:
                return league
        raise KeyError(f"no league at tier {tier}")

    def matches_in_week(self, week_number: int) -> list[Match]:
        return [
            m for m in self.matches.values()
            if m.season_id == self.season.id and m.week_number == week_number
        ]

    def user_match_in_week(self, week_number: int) -> Match | None:
        """The user's club's fixture in a given match week, if any."""
        if self.user_club_id is None:
            return None
        for match in self.matches_in_week(week_number):
            if self.user_club_id in (match.home_club_id, match.away_club_id):
                return match
        return None

    def contract_for(self, player_id: int) -> Contract | None:
        player = self.players.get(player_id)
        if player is None or player.contract_id is None:
            return None
        return self.contracts.get(player.contract_id)

    def pending_offers_for_user(self) -> list[TransferOffer]:
        from touchline.engine.models import OfferStatus

        if self.user_player_id is None:
            return []
        return [
            o for o in self.transfer_offers.values()
            if o.player_id == self.user_player_id
            and o.status == OfferStatus.PENDING_USER_DECISION
        ]

    def career_totals(self) -> dict:
        """Lifetime totals aggregated from the user's season records."""
        apps = sum(r.appearances for r in self.season_records)
        goals = sum(r.goals for r in self.season_records)
        assists = sum(r.assists for r in self.season_records)
        rated = [(r.avg_rating, r.appearances)
                 for r in self.season_records if r.appearances]
        weighted = sum(rating * n for rating, n in rated)
        total_apps = sum(n for _, n in rated)
        avg = round(weighted / total_apps, 2) if total_apps else 0.0
        return {
            "seasons": len(self.season_records),
            "appearances": apps,
            "goals": goals,
            "assists": assists,
            "avg_rating": avg,
            "honours": len(self.honours),
        }
