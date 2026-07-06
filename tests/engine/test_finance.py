"""Tests for club finances: balances, wage bills, transfers, and settlement."""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine import finance, transfers
from touchline.engine.career import advance_week, new_career
from touchline.engine.models import ATTRIBUTE_NAMES, OfferStatus, Position


def _career(seed=1):
    return new_career("Fin", "Leo", "Silva", Position.FW, random.Random(seed))


def test_clubs_start_with_reputation_scaled_balance():
    state = _career()
    for club in state.clubs.values():
        assert club.balance == club.reputation * C.CLUB_BALANCE_PER_REP
        assert club.balance > 0


def test_wage_bill_and_squad_value_are_positive():
    state = _career()
    club = state.user_club
    assert finance.weekly_wage_bill(state, club) > 0
    assert finance.squad_value(state, club) > 0


def test_transfer_completion_moves_money_between_clubs():
    state = _career()
    player = state.user_player
    from_club = state.clubs[player.club_id]
    suitor = next(c for c in state.clubs.values() if c.id != from_club.id)
    suitor.balance = 10 ** 9

    offer = transfers._make_offer(state, suitor, player, random.Random(0))
    offer.status = OfferStatus.PENDING_USER_DECISION
    state.transfer_offers[offer.id] = offer

    buyer_before, seller_before = suitor.balance, from_club.balance
    transfers.respond_to_offer(state, offer.id, "accept", random.Random(0))

    assert suitor.balance == buyer_before - offer.offer_fee
    assert from_club.balance == seller_before + offer.offer_fee


def test_broke_clubs_cannot_sign_the_user():
    state = _career(3)
    player = state.user_player
    for attr in ATTRIBUTE_NAMES:
        setattr(player, attr, 90)  # elite: lots of interest...
    for club in state.clubs.values():
        if club.id != player.club_id:
            club.balance = 0        # ...but nobody can pay the fee

    rng = random.Random(1)
    for _ in range(100):
        transfers.roll_transfer_interest(state, rng)
    assert not state.pending_offers_for_user()


def test_season_settlement_keeps_clubs_solvent_and_rewards_finishing():
    state = _career(2)
    rng = random.Random(2)
    before = {c.id: c.balance for c in state.clubs.values()}

    while state.season.current_week < C.SEASON_END_WEEK:
        advance_week(state, rng)
    advance_week(state, rng)  # season-end settlement runs here

    for club in state.clubs.values():
        assert club.balance >= 0
    # Prize money + operating surplus means balances grew overall.
    assert any(c.balance > before[c.id] for c in state.clubs.values())
