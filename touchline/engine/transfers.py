"""Transfer interest, valuation, and negotiation for the user's player.

Deliberate v1 scope: only the user participates in the market. AI clubs change
their squads only through aging, retirement, and youth intake — a full AI-to-AI
market is out of scope. Interest is rolled weekly (window permitting) against a
shortlist of reputation-plausible suitors; a small state machine drives the
negotiation from a club bid to a completed move.
"""

from __future__ import annotations

import random
import statistics

from touchline.engine import constants as C
from touchline.engine.models import Contract, OfferStatus, Player, TransferOffer
from touchline.engine.rng import clamp
from touchline.engine.state import GameState


# --------------------------------------------------------------------------- #
# Valuation
# --------------------------------------------------------------------------- #


def age_curve(age: int) -> float:
    """Value multiplier by age, peaking in the mid-20s."""
    if age <= 18:
        return 0.7
    if age <= 23:
        return 0.9
    if age <= 27:
        return 1.0
    if age <= 30:
        return 0.8
    if age <= 33:
        return 0.5
    return 0.3


def transfer_fee(player: Player) -> int:
    """A club's valuation of a player (abstract currency)."""
    overall = player.overall()
    potential_factor = 0.5 + player.potential / 200
    return int(overall * overall * age_curve(player.age) * potential_factor
               * C.TIER_VALUE_SCALE)


def _current_wage(state: GameState, player: Player) -> int:
    contract = state.contract_for(player.id)
    if contract is not None:
        return contract.wage_per_week
    return max(50, int(player.overall() ** 2 / 15))


# --------------------------------------------------------------------------- #
# Interest
# --------------------------------------------------------------------------- #


def _performance_factor(state: GameState, player: Player) -> float:
    stats = [s for s in state.player_stats if s.player_id == player.id]
    if not stats:
        return 0.6  # unproven this season
    avg_rating = statistics.mean(s.rating for s in stats)
    goals = sum(s.goals for s in stats)
    return clamp(avg_rating - 5.5, 0.1, 2.5) + goals * 0.05


def _attribute_fit_factor(state: GameState, suitor, player: Player) -> float:
    same_position = [p for p in state.squad(suitor.id) if p.position == player.position]
    suitor_level = statistics.mean(p.overall() for p in same_position) if same_position else 50
    return clamp(1.0 + (player.overall() - suitor_level) / 25, 0.2, 2.0)


def _contract_factor(state: GameState, player: Player) -> float:
    contract = state.contract_for(player.id)
    if contract is None:
        return 2.0  # free agent
    weeks_left = contract.expires_on_week - state.current_week
    if weeks_left <= C.SEASON_LENGTH:
        return 1.6
    if weeks_left <= 2 * C.SEASON_LENGTH:
        return 1.2
    return 1.0


def _reputation_fit_factor(suitor, current) -> float:
    # Smaller reputation gap between clubs = a more plausible move.
    gap = abs(suitor.reputation - current.reputation)
    return clamp(1.5 - gap / 30, 0.1, 1.5)


def interest_probability(state: GameState, suitor, player: Player) -> float:
    """Weekly probability a specific suitor makes a move for the player."""
    current = state.clubs.get(player.club_id)
    reputation_factor = _reputation_fit_factor(suitor, current) if current else 1.0
    probability = (
        C.TRANSFER_BASE_RATE
        * _performance_factor(state, player)
        * _attribute_fit_factor(state, suitor, player)
        * _contract_factor(state, player)
        * reputation_factor
    )
    return clamp(probability, 0.0, C.TRANSFER_PROB_CAP)


def _candidate_suitors(state: GameState, player: Player) -> list:
    current = state.clubs.get(player.club_id)
    anchor = max(current.reputation, player.overall()) if current else player.overall()
    suitors = [
        c for c in state.clubs.values()
        if c.id != player.club_id
        and abs(c.reputation - anchor) <= C.TRANSFER_REP_BAND
    ]
    suitors.sort(key=lambda c: abs(c.reputation - anchor))
    return suitors[: C.MAX_SUITORS_CONSIDERED]


def _make_offer(state: GameState, suitor, player: Player, rng: random.Random) -> TransferOffer:
    fee = int(transfer_fee(player) * rng.uniform(0.9, 1.3))
    base_wage = _current_wage(state, player)
    wage = int(base_wage * rng.uniform(1.1, 1.4))
    if player.age <= 27:
        length = rng.randint(3, 5)
    elif player.age <= 31:
        length = rng.randint(2, 3)
    else:
        length = rng.randint(1, 2)
    return TransferOffer(
        id=state.next_id(),
        player_id=player.id,
        from_club_id=player.club_id if player.club_id else suitor.id,
        to_club_id=suitor.id,
        offer_fee=fee,
        wage_offered=wage,
        length_offered_years=length,
        status=OfferStatus.PENDING_CLUB_DECISION,
        week_created=state.current_week,
    )


def _current_club_accepts(state: GameState, offer: TransferOffer, rng: random.Random) -> bool:
    player = state.players[offer.player_id]
    current = state.clubs.get(offer.from_club_id)
    suitor = state.clubs[offer.to_club_id]
    if current is None or current.id == suitor.id:
        return True  # free agent: no selling club to convince
    probability = 0.3
    if suitor.reputation > current.reputation:
        probability += 0.3
    contract = state.contract_for(player.id)
    if contract is not None and contract.expires_on_week - state.current_week <= C.SEASON_LENGTH:
        probability += 0.3
    if offer.offer_fee >= transfer_fee(player) * 1.1:
        probability += 0.2
    return rng.random() < clamp(probability, 0.05, 0.95)


def roll_transfer_interest(state: GameState, rng: random.Random) -> list[str]:
    """Generate at most one new actionable offer for the user this week."""
    messages: list[str] = []
    player = state.user_player
    if player is None or player.is_retired:
        return messages
    if len(state.pending_offers_for_user()) >= C.MAX_PENDING_OFFERS:
        return messages

    for suitor in _candidate_suitors(state, player):
        if rng.random() >= interest_probability(state, suitor, player):
            continue
        offer = _make_offer(state, suitor, player, rng)
        if suitor.balance < offer.offer_fee:
            continue  # the suitor can't afford the fee
        state.transfer_offers[offer.id] = offer
        if _current_club_accepts(state, offer, rng):
            offer.status = OfferStatus.PENDING_USER_DECISION
            offer.history.append(
                f"{suitor.name} offered {offer.offer_fee} and {offer.wage_offered}/week."
            )
            messages.append(f"📩 {suitor.name} want to sign you — check your transfer inbox.")
            break  # one actionable offer per week is plenty
        offer.status = OfferStatus.REJECTED_BY_CLUB
    return messages


# --------------------------------------------------------------------------- #
# Negotiation
# --------------------------------------------------------------------------- #


def respond_to_offer(
    state: GameState, offer_id: int, action: str, rng: random.Random
) -> list[str]:
    """Apply the user's decision on an offer: accept, reject, or counter."""
    offer = state.transfer_offers.get(offer_id)
    if offer is None or offer.status != OfferStatus.PENDING_USER_DECISION:
        return ["That offer is no longer available."]
    if action == "accept":
        return _complete_transfer(state, offer)
    if action == "reject":
        offer.status = OfferStatus.WITHDRAWN
        return [f"You turned down {state.clubs[offer.to_club_id].name}."]
    if action == "counter":
        return _counter_wage(state, offer, rng)
    return ["Unknown response."]


def _complete_transfer(state: GameState, offer: TransferOffer) -> list[str]:
    player = state.players[offer.player_id]
    to_club = state.clubs[offer.to_club_id]

    # Money changes hands: the buyer pays the fee, the selling club receives it.
    to_club.balance -= offer.offer_fee
    from_club = state.clubs.get(offer.from_club_id)
    if from_club is not None and from_club.id != to_club.id:
        from_club.balance += offer.offer_fee

    if player.contract_id is not None:
        state.contracts.pop(player.contract_id, None)
    contract = Contract(
        id=state.next_id(),
        player_id=player.id,
        club_id=to_club.id,
        wage_per_week=offer.wage_offered,
        signed_on_week=state.current_week,
        expires_on_week=state.current_week + offer.length_offered_years * C.SEASON_LENGTH,
    )
    state.contracts[contract.id] = contract
    player.contract_id = contract.id
    player.club_id = to_club.id
    offer.status = OfferStatus.COMPLETED
    if player.is_user:
        state.user_club_id = to_club.id

    # Withdraw any other pending offers for this player.
    for other in state.transfer_offers.values():
        if (other.id != offer.id and other.player_id == player.id
                and other.status == OfferStatus.PENDING_USER_DECISION):
            other.status = OfferStatus.WITHDRAWN

    return [f"✍️ Transfer complete! You've signed for {to_club.name} "
            f"on {offer.wage_offered}/week for {offer.length_offered_years} year(s)."]


def _counter_wage(state: GameState, offer: TransferOffer, rng: random.Random) -> list[str]:
    if offer.length_offered_years < 0 or any("counter" in h for h in offer.history):
        return ["You have already countered this offer once."]
    to_club = state.clubs[offer.to_club_id]
    demanded = int(offer.wage_offered * C.WAGE_COUNTER_MULTIPLIER)
    ceiling = int(offer.wage_offered * C.WAGE_COUNTER_CEILING)
    offer.history.append(f"counter: you demanded {demanded}/week.")
    if demanded <= ceiling and to_club.wage_budget >= demanded:
        offer.wage_offered = demanded
        offer.history.append(f"{to_club.name} agreed to {demanded}/week.")
        return [f"{to_club.name} accepted your demand of {demanded}/week. You can now accept."]
    offer.status = OfferStatus.WITHDRAWN
    offer.history.append(f"{to_club.name} pulled out after your demand.")
    return [f"{to_club.name} refused your wage demand and walked away."]
