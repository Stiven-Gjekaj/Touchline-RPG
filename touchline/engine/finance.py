"""Club finances: wage bills, squad value, and the season-end settlement.

Kept deliberately simple for v1.1: balances change through transfer fees and a
once-a-season settlement calibrated so clubs stay solvent (income slightly
exceeds wages), plus prize money for a higher league finish.
"""

from __future__ import annotations

from touchline.engine import constants as C
from touchline.engine.models import Club
from touchline.engine.state import GameState


def weekly_wage_bill(state: GameState, club: Club) -> int:
    """Total weekly wages of a club's contracted players."""
    total = 0
    for player in state.squad(club.id):
        contract = state.contract_for(player.id)
        if contract is not None:
            total += contract.wage_per_week
    return total


def squad_value(state: GameState, club: Club) -> int:
    """Sum of the squad's transfer valuations."""
    from touchline.engine.transfers import transfer_fee

    return sum(transfer_fee(p) for p in state.squad(club.id))


def settle_season(state: GameState, standings_lookup) -> None:
    """Apply each club's season financial result to its balance.

    ``standings_lookup(club)`` returns the club's 1-based finishing position in
    its division. Net result = a small operating surplus + prize money.
    """
    for club in state.clubs.values():
        wages = weekly_wage_bill(state, club) * C.MATCH_WEEKS
        position = standings_lookup(club)
        prize_per_place = C.PRIZE_MONEY_PER_PLACE.get(club.division_tier, 0)
        prize = prize_per_place * (C.CLUBS_PER_TIER - position + 1)
        operating_surplus = int(wages * C.OPERATING_SURPLUS)
        club.balance += operating_surplus + prize
