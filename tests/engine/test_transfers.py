"""Tests for transfer interest, valuation, and the negotiation state machine."""

from __future__ import annotations

import random

from touchline.engine import transfers
from touchline.engine.career import new_career
from touchline.engine.models import (
    ATTRIBUTE_NAMES,
    MatchPlayerStat,
    OfferStatus,
    Position,
)


def _career(seed=1):
    rng = random.Random(seed)
    return new_career("T", "Leo", "Silva", Position.FW, rng), rng


def _add_stat(state, player_id, rating, goals=0, assists=0):
    state.player_stats.append(MatchPlayerStat(
        id=state.next_id(), match_id=1, player_id=player_id,
        goals=goals, assists=assists, rating=rating, minutes_played=90,
    ))


def _a_suitor(state):
    player = state.user_player
    return next(c for c in state.clubs.values() if c.id != player.club_id)


# --------------------------------------------------------------------------- #
# Interest — directional
# --------------------------------------------------------------------------- #


def test_interest_rises_with_performance():
    state, _ = _career()
    player = state.user_player
    suitor = _a_suitor(state)

    low = transfers.interest_probability(state, suitor, player)
    for _ in range(5):
        _add_stat(state, player.id, rating=9.0, goals=2, assists=1)
    high = transfers.interest_probability(state, suitor, player)
    assert high > low


def test_reputation_fit_prefers_smaller_gaps():
    state, _ = _career()
    current = state.user_club

    class Fake:
        pass

    near = Fake(); near.reputation = current.reputation + 3
    far = Fake(); far.reputation = current.reputation + 25
    assert (transfers._reputation_fit_factor(near, current)
            > transfers._reputation_fit_factor(far, current))


# --------------------------------------------------------------------------- #
# Valuation
# --------------------------------------------------------------------------- #


def test_fee_is_positive_and_rises_with_overall():
    state, _ = _career()
    player = state.user_player
    weak_fee = transfers.transfer_fee(player)
    for attr in ATTRIBUTE_NAMES:
        setattr(player, attr, 90)
    strong_fee = transfers.transfer_fee(player)
    assert weak_fee > 0
    assert strong_fee > weak_fee


def test_age_curve_peaks_in_mid_twenties():
    assert transfers.age_curve(25) > transfers.age_curve(18)
    assert transfers.age_curve(25) > transfers.age_curve(34)


# --------------------------------------------------------------------------- #
# Negotiation state machine
# --------------------------------------------------------------------------- #


def _pending_offer(state, rng):
    player = state.user_player
    suitor = _a_suitor(state)
    offer = transfers._make_offer(state, suitor, player, rng)
    offer.status = OfferStatus.PENDING_USER_DECISION
    state.transfer_offers[offer.id] = offer
    return offer, suitor


def test_accept_completes_transfer_and_moves_player():
    state, rng = _career()
    player = state.user_player
    old_club = player.club_id
    offer, suitor = _pending_offer(state, rng)

    transfers.respond_to_offer(state, offer.id, "accept", rng)

    assert offer.status == OfferStatus.COMPLETED
    assert player.club_id == suitor.id != old_club
    assert state.user_club_id == suitor.id
    contract = state.contract_for(player.id)
    assert contract is not None and contract.club_id == suitor.id


def test_accept_withdraws_other_pending_offers():
    state, rng = _career()
    offer_a, _ = _pending_offer(state, rng)
    offer_b, _ = _pending_offer(state, rng)
    transfers.respond_to_offer(state, offer_a.id, "accept", rng)
    assert offer_b.status == OfferStatus.WITHDRAWN


def test_reject_withdraws_offer():
    state, rng = _career()
    offer, _ = _pending_offer(state, rng)
    transfers.respond_to_offer(state, offer.id, "reject", rng)
    assert offer.status == OfferStatus.WITHDRAWN


def test_counter_within_ceiling_is_accepted_then_capped_to_one():
    state, rng = _career()
    offer, suitor = _pending_offer(state, rng)
    suitor.wage_budget = 10 ** 9
    old_wage = offer.wage_offered

    transfers.respond_to_offer(state, offer.id, "counter", rng)
    assert offer.wage_offered > old_wage
    assert offer.status == OfferStatus.PENDING_USER_DECISION

    result = transfers.respond_to_offer(state, offer.id, "counter", rng)
    assert "already countered" in result[0].lower()


def test_counter_beyond_budget_pulls_club_out():
    state, rng = _career()
    offer, suitor = _pending_offer(state, rng)
    suitor.wage_budget = 0
    transfers.respond_to_offer(state, offer.id, "counter", rng)
    assert offer.status == OfferStatus.WITHDRAWN


def test_respond_to_stale_offer_is_safe():
    state, rng = _career()
    offer, _ = _pending_offer(state, rng)
    offer.status = OfferStatus.WITHDRAWN
    result = transfers.respond_to_offer(state, offer.id, "accept", rng)
    assert "no longer available" in result[0].lower()


# --------------------------------------------------------------------------- #
# End-to-end interest generation
# --------------------------------------------------------------------------- #


def test_standout_player_eventually_attracts_an_offer():
    state, _ = _career(seed=7)
    player = state.user_player
    for attr in ATTRIBUTE_NAMES:
        setattr(player, attr, 88)
    for _ in range(6):
        _add_stat(state, player.id, rating=9.0, goals=2, assists=1)

    rng = random.Random(3)
    attracted = False
    for _ in range(300):
        transfers.roll_transfer_interest(state, rng)
        if state.pending_offers_for_user():
            attracted = True
            break
    assert attracted
