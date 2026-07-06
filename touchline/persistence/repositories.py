"""Whole-graph persistence: save and load an entire :class:`GameState`.

A save is small (a few thousand rows) and single-user, so each save rewrites all
rows inside one transaction. That trades a little I/O for total simplicity and
guaranteed consistency — no change-tracking or delete-reconciliation to get wrong.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from touchline.engine.constants import SCHEMA_VERSION
from touchline.engine.models import Mentality, Tactic
from touchline.engine.state import GameState
from touchline.persistence import mappers as m
from touchline.persistence import orm_models as orm


class IncompatibleSaveError(Exception):
    """Raised when a save file's schema version doesn't match the game."""


def schema_version(session: Session) -> int | None:
    """Read the save's schema version via a column present in every version.

    Done with raw SQL so it works even when newer columns are absent from an
    older file (a full ORM read would fail on the missing columns).
    """
    try:
        row = session.execute(text("SELECT schema_version FROM meta WHERE id = 1")).first()
        return int(row[0]) if row else None
    except Exception:
        return None


_ROW_TYPES = [
    orm.MetaRow, orm.CountryRow, orm.SeasonRow, orm.LeagueRow, orm.ClubRow,
    orm.PlayerRow, orm.MatchRow, orm.MatchEventRow, orm.MatchPlayerStatRow,
    orm.ContractRow, orm.TransferOfferRow, orm.SeasonRecordRow, orm.HonourRow,
]


def save_state(session: Session, state: GameState) -> None:
    """Persist the entire game state, replacing any prior contents."""
    for row_type in _ROW_TYPES:
        session.query(row_type).delete()

    session.add(orm.MetaRow(
        id=1, save_name=state.save_name, created_at=state.created_at,
        last_played_at=state.last_played_at, schema_version=state.schema_version,
        user_player_id=state.user_player_id, user_club_id=state.user_club_id,
        next_id=state._next_id, season_id=state.season.id,
        formation=state.tactic.formation, mentality=state.tactic.mentality.value,
    ))
    session.add(m.country_to_row(state.country))
    session.add(m.season_to_row(state.season))
    session.add_all(m.league_to_row(x) for x in state.leagues.values())
    session.add_all(m.club_to_row(x) for x in state.clubs.values())
    session.add_all(m.player_to_row(x) for x in state.players.values())
    session.add_all(m.match_to_row(x) for x in state.matches.values())
    session.add_all(m.event_to_row(x) for x in state.events)
    session.add_all(m.stat_to_row(x) for x in state.player_stats)
    session.add_all(m.contract_to_row(x) for x in state.contracts.values())
    session.add_all(m.offer_to_row(x) for x in state.transfer_offers.values())
    session.add_all(m.season_record_to_row(x) for x in state.season_records)
    session.add_all(m.honour_to_row(x) for x in state.honours)
    session.commit()


def load_state(session: Session, expected_version: int = SCHEMA_VERSION) -> GameState:
    """Reconstruct a :class:`GameState` from a save, or raise if incompatible."""
    version = schema_version(session)
    if version is None:
        raise IncompatibleSaveError("save file has no metadata row")
    if version != expected_version:
        raise IncompatibleSaveError(
            f"save schema v{version} is incompatible with "
            f"game schema v{expected_version}"
        )

    meta = session.get(orm.MetaRow, 1)
    country = m.country_from_row(session.query(orm.CountryRow).one())
    season = m.season_from_row(session.get(orm.SeasonRow, meta.season_id))
    mentality = Mentality(meta.mentality) if meta.mentality else Mentality.BALANCED
    tactic = Tactic(formation=meta.formation or "4-4-2", mentality=mentality)
    state = GameState(
        save_name=meta.save_name, created_at=meta.created_at,
        last_played_at=meta.last_played_at, schema_version=meta.schema_version,
        country=country, season=season, user_player_id=meta.user_player_id,
        user_club_id=meta.user_club_id, _next_id=meta.next_id, tactic=tactic,
    )
    for row in session.query(orm.LeagueRow).all():
        league = m.league_from_row(row)
        state.leagues[league.id] = league
    for row in session.query(orm.ClubRow).all():
        club = m.club_from_row(row)
        state.clubs[club.id] = club
    for row in session.query(orm.PlayerRow).all():
        player = m.player_from_row(row)
        state.players[player.id] = player
    for row in session.query(orm.MatchRow).all():
        match = m.match_from_row(row)
        state.matches[match.id] = match
    for row in session.query(orm.ContractRow).all():
        contract = m.contract_from_row(row)
        state.contracts[contract.id] = contract
    for row in session.query(orm.TransferOfferRow).all():
        offer = m.offer_from_row(row)
        state.transfer_offers[offer.id] = offer
    state.events = [m.event_from_row(r) for r in session.query(orm.MatchEventRow).all()]
    state.player_stats = [m.stat_from_row(r)
                          for r in session.query(orm.MatchPlayerStatRow).all()]
    state.season_records = [
        m.season_record_from_row(r)
        for r in session.query(orm.SeasonRecordRow).order_by(orm.SeasonRecordRow.id).all()
    ]
    state.honours = [
        m.honour_from_row(r)
        for r in session.query(orm.HonourRow).order_by(orm.HonourRow.id).all()
    ]
    return state
