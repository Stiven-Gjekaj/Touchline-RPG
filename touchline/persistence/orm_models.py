"""SQLAlchemy ORM models mirroring the engine dataclasses.

These are the persisted shapes. Mappers translate them to and from the pure
engine dataclasses so the engine never imports SQLAlchemy. No relationships or
foreign-key constraints are declared — the graph is reassembled by id in Python,
which keeps the whole-graph save (delete-all then insert) order-independent.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, Float, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class MetaRow(Base):
    __tablename__ = "meta"
    id = Column(Integer, primary_key=True)  # always 1
    save_name = Column(String, nullable=False)
    created_at = Column(String, nullable=False)
    last_played_at = Column(String, nullable=False)
    schema_version = Column(Integer, nullable=False)
    user_player_id = Column(Integer)
    user_club_id = Column(Integer)
    next_id = Column(Integer, nullable=False)
    season_id = Column(Integer, nullable=False)
    formation = Column(String)
    mentality = Column(String)


class CountryRow(Base):
    __tablename__ = "country"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)


class SeasonRow(Base):
    __tablename__ = "season"
    id = Column(Integer, primary_key=True)
    number = Column(Integer, nullable=False)
    current_week = Column(Integer, nullable=False)
    is_complete = Column(Boolean, nullable=False)


class LeagueRow(Base):
    __tablename__ = "leagues"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    tier = Column(Integer, nullable=False)
    country_id = Column(Integer, nullable=False)
    promotion_slots = Column(Integer, nullable=False)
    relegation_slots = Column(Integer, nullable=False)


class ClubRow(Base):
    __tablename__ = "clubs"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    short_name = Column(String, nullable=False)
    league_id = Column(Integer, nullable=False)
    division_tier = Column(Integer, nullable=False)
    reputation = Column(Integer, nullable=False)
    wage_budget = Column(Integer, nullable=False)
    balance = Column(Integer, nullable=False, default=0)


class PlayerRow(Base):
    __tablename__ = "players"
    id = Column(Integer, primary_key=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    age = Column(Integer, nullable=False)
    position = Column(String, nullable=False)
    nationality = Column(String, nullable=False)
    club_id = Column(Integer)
    pace = Column(Integer, nullable=False)
    shooting = Column(Integer, nullable=False)
    passing = Column(Integer, nullable=False)
    defending = Column(Integer, nullable=False)
    physical = Column(Integer, nullable=False)
    goalkeeping = Column(Integer, nullable=False)
    potential = Column(Integer, nullable=False)
    form = Column(Integer, nullable=False)
    morale = Column(Integer, nullable=False)
    condition = Column(Integer, nullable=False)
    injury_weeks_remaining = Column(Integer, nullable=False)
    is_user = Column(Boolean, nullable=False)
    is_retired = Column(Boolean, nullable=False)
    contract_id = Column(Integer)
    sub_position = Column(String)


class MatchRow(Base):
    __tablename__ = "matches"
    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, nullable=False)
    week_number = Column(Integer, nullable=False)
    home_club_id = Column(Integer, nullable=False)
    away_club_id = Column(Integer, nullable=False)
    home_goals = Column(Integer)
    away_goals = Column(Integer)
    is_played = Column(Boolean, nullable=False)


class MatchEventRow(Base):
    __tablename__ = "match_events"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, nullable=False)
    minute = Column(Integer, nullable=False)
    event_type = Column(String, nullable=False)
    club_id = Column(Integer, nullable=False)
    player_id = Column(Integer)
    description = Column(String, nullable=False)


class MatchPlayerStatRow(Base):
    __tablename__ = "match_player_stats"
    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, nullable=False)
    player_id = Column(Integer, nullable=False)
    goals = Column(Integer, nullable=False)
    assists = Column(Integer, nullable=False)
    rating = Column(Float, nullable=False)
    minutes_played = Column(Integer, nullable=False)
    was_injured = Column(Boolean, nullable=False)


class ContractRow(Base):
    __tablename__ = "contracts"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, nullable=False)
    club_id = Column(Integer, nullable=False)
    wage_per_week = Column(Integer, nullable=False)
    signed_on_week = Column(Integer, nullable=False)
    expires_on_week = Column(Integer, nullable=False)


class TransferOfferRow(Base):
    __tablename__ = "transfer_offers"
    id = Column(Integer, primary_key=True)
    player_id = Column(Integer, nullable=False)
    from_club_id = Column(Integer, nullable=False)
    to_club_id = Column(Integer, nullable=False)
    offer_fee = Column(Integer, nullable=False)
    wage_offered = Column(Integer, nullable=False)
    length_offered_years = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    week_created = Column(Integer, nullable=False)
    history = Column(Text, nullable=False, default="[]")


class SeasonRecordRow(Base):
    __tablename__ = "season_records"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season_number = Column(Integer, nullable=False)
    club_name = Column(String, nullable=False)
    division_name = Column(String, nullable=False)
    appearances = Column(Integer, nullable=False)
    goals = Column(Integer, nullable=False)
    assists = Column(Integer, nullable=False)
    avg_rating = Column(Float, nullable=False)
    league_position = Column(Integer)


class HonourRow(Base):
    __tablename__ = "honours"
    id = Column(Integer, primary_key=True, autoincrement=True)
    season_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)


class CupRow(Base):
    __tablename__ = "cup"
    id = Column(Integer, primary_key=True)  # always 1
    name = Column(String, nullable=False)
    round_size = Column(Integer, nullable=False)
    champion_club_id = Column(Integer)
    is_complete = Column(Boolean, nullable=False)


class CupTieRow(Base):
    __tablename__ = "cup_ties"
    id = Column(Integer, primary_key=True)
    round_size = Column(Integer, nullable=False)
    week_number = Column(Integer, nullable=False)
    home_club_id = Column(Integer, nullable=False)
    away_club_id = Column(Integer, nullable=False)
    home_goals = Column(Integer)
    away_goals = Column(Integer)
    winner_club_id = Column(Integer)
    is_played = Column(Boolean, nullable=False)
    decided_on_penalties = Column(Boolean, nullable=False)
