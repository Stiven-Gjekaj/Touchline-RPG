"""Translation between engine dataclasses and ORM rows.

Kept explicit (one function per direction per entity) so the mapping is obvious
and enum/JSON handling is in one place.
"""

from __future__ import annotations

import json

from touchline.engine.models import (
    Club,
    Contract,
    Country,
    EventType,
    Honour,
    League,
    Match,
    MatchEvent,
    MatchPlayerStat,
    OfferStatus,
    Player,
    Position,
    Season,
    SeasonRecord,
    SubPosition,
    TransferOffer,
)
from touchline.persistence import orm_models as orm


def country_to_row(country: Country) -> orm.CountryRow:
    return orm.CountryRow(id=country.id, name=country.name)


def country_from_row(row: orm.CountryRow) -> Country:
    return Country(id=row.id, name=row.name)


def season_to_row(season: Season) -> orm.SeasonRow:
    return orm.SeasonRow(id=season.id, number=season.number,
                         current_week=season.current_week,
                         is_complete=season.is_complete)


def season_from_row(row: orm.SeasonRow) -> Season:
    return Season(id=row.id, number=row.number, current_week=row.current_week,
                  is_complete=row.is_complete)


def league_to_row(league: League) -> orm.LeagueRow:
    return orm.LeagueRow(id=league.id, name=league.name, tier=league.tier,
                         country_id=league.country_id,
                         promotion_slots=league.promotion_slots,
                         relegation_slots=league.relegation_slots)


def league_from_row(row: orm.LeagueRow) -> League:
    return League(id=row.id, name=row.name, tier=row.tier,
                  country_id=row.country_id, promotion_slots=row.promotion_slots,
                  relegation_slots=row.relegation_slots)


def club_to_row(club: Club) -> orm.ClubRow:
    return orm.ClubRow(id=club.id, name=club.name, short_name=club.short_name,
                       league_id=club.league_id, division_tier=club.division_tier,
                       reputation=club.reputation, wage_budget=club.wage_budget)


def club_from_row(row: orm.ClubRow) -> Club:
    return Club(id=row.id, name=row.name, short_name=row.short_name,
                league_id=row.league_id, division_tier=row.division_tier,
                reputation=row.reputation, wage_budget=row.wage_budget)


def player_to_row(player: Player) -> orm.PlayerRow:
    return orm.PlayerRow(
        id=player.id, first_name=player.first_name, last_name=player.last_name,
        age=player.age, position=player.position.value,
        nationality=player.nationality, club_id=player.club_id,
        pace=player.pace, shooting=player.shooting, passing=player.passing,
        defending=player.defending, physical=player.physical,
        goalkeeping=player.goalkeeping, potential=player.potential,
        form=player.form, morale=player.morale, condition=player.condition,
        injury_weeks_remaining=player.injury_weeks_remaining,
        is_user=player.is_user, is_retired=player.is_retired,
        contract_id=player.contract_id,
        sub_position=player.sub_position.value if player.sub_position else None,
    )


def player_from_row(row: orm.PlayerRow) -> Player:
    return Player(
        id=row.id, first_name=row.first_name, last_name=row.last_name,
        age=row.age, position=Position(row.position), nationality=row.nationality,
        club_id=row.club_id, pace=row.pace, shooting=row.shooting,
        passing=row.passing, defending=row.defending, physical=row.physical,
        goalkeeping=row.goalkeeping, potential=row.potential, form=row.form,
        morale=row.morale, condition=row.condition,
        injury_weeks_remaining=row.injury_weeks_remaining, is_user=row.is_user,
        is_retired=row.is_retired, contract_id=row.contract_id,
        sub_position=SubPosition(row.sub_position) if row.sub_position else None,
    )


def match_to_row(match: Match) -> orm.MatchRow:
    return orm.MatchRow(id=match.id, season_id=match.season_id,
                        week_number=match.week_number,
                        home_club_id=match.home_club_id,
                        away_club_id=match.away_club_id,
                        home_goals=match.home_goals, away_goals=match.away_goals,
                        is_played=match.is_played)


def match_from_row(row: orm.MatchRow) -> Match:
    return Match(id=row.id, season_id=row.season_id, week_number=row.week_number,
                 home_club_id=row.home_club_id, away_club_id=row.away_club_id,
                 home_goals=row.home_goals, away_goals=row.away_goals,
                 is_played=row.is_played)


def event_to_row(event: MatchEvent) -> orm.MatchEventRow:
    return orm.MatchEventRow(id=event.id, match_id=event.match_id,
                             minute=event.minute,
                             event_type=event.event_type.value,
                             club_id=event.club_id, player_id=event.player_id,
                             description=event.description)


def event_from_row(row: orm.MatchEventRow) -> MatchEvent:
    return MatchEvent(id=row.id, match_id=row.match_id, minute=row.minute,
                      event_type=EventType(row.event_type), club_id=row.club_id,
                      player_id=row.player_id, description=row.description)


def stat_to_row(stat: MatchPlayerStat) -> orm.MatchPlayerStatRow:
    return orm.MatchPlayerStatRow(id=stat.id, match_id=stat.match_id,
                                  player_id=stat.player_id, goals=stat.goals,
                                  assists=stat.assists, rating=stat.rating,
                                  minutes_played=stat.minutes_played,
                                  was_injured=stat.was_injured)


def stat_from_row(row: orm.MatchPlayerStatRow) -> MatchPlayerStat:
    return MatchPlayerStat(id=row.id, match_id=row.match_id,
                           player_id=row.player_id, goals=row.goals,
                           assists=row.assists, rating=row.rating,
                           minutes_played=row.minutes_played,
                           was_injured=row.was_injured)


def contract_to_row(contract: Contract) -> orm.ContractRow:
    return orm.ContractRow(id=contract.id, player_id=contract.player_id,
                           club_id=contract.club_id,
                           wage_per_week=contract.wage_per_week,
                           signed_on_week=contract.signed_on_week,
                           expires_on_week=contract.expires_on_week)


def contract_from_row(row: orm.ContractRow) -> Contract:
    return Contract(id=row.id, player_id=row.player_id, club_id=row.club_id,
                    wage_per_week=row.wage_per_week,
                    signed_on_week=row.signed_on_week,
                    expires_on_week=row.expires_on_week)


def offer_to_row(offer: TransferOffer) -> orm.TransferOfferRow:
    return orm.TransferOfferRow(id=offer.id, player_id=offer.player_id,
                                from_club_id=offer.from_club_id,
                                to_club_id=offer.to_club_id,
                                offer_fee=offer.offer_fee,
                                wage_offered=offer.wage_offered,
                                length_offered_years=offer.length_offered_years,
                                status=offer.status.value,
                                week_created=offer.week_created,
                                history=json.dumps(offer.history))


def offer_from_row(row: orm.TransferOfferRow) -> TransferOffer:
    return TransferOffer(id=row.id, player_id=row.player_id,
                         from_club_id=row.from_club_id, to_club_id=row.to_club_id,
                         offer_fee=row.offer_fee, wage_offered=row.wage_offered,
                         length_offered_years=row.length_offered_years,
                         status=OfferStatus(row.status),
                         week_created=row.week_created,
                         history=json.loads(row.history or "[]"))


def season_record_to_row(record: SeasonRecord) -> orm.SeasonRecordRow:
    return orm.SeasonRecordRow(
        season_number=record.season_number, club_name=record.club_name,
        division_name=record.division_name, appearances=record.appearances,
        goals=record.goals, assists=record.assists, avg_rating=record.avg_rating,
        league_position=record.league_position)


def season_record_from_row(row: orm.SeasonRecordRow) -> SeasonRecord:
    return SeasonRecord(
        season_number=row.season_number, club_name=row.club_name,
        division_name=row.division_name, appearances=row.appearances,
        goals=row.goals, assists=row.assists, avg_rating=row.avg_rating,
        league_position=row.league_position)


def honour_to_row(honour: Honour) -> orm.HonourRow:
    return orm.HonourRow(season_number=honour.season_number, title=honour.title)


def honour_from_row(row: orm.HonourRow) -> Honour:
    return Honour(season_number=row.season_number, title=row.title)
