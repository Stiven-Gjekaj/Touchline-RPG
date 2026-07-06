"""Tests for the knockout cup."""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine import cup
from touchline.engine.career import advance_week, new_career
from touchline.engine.models import ATTRIBUTE_NAMES, Cup, CupTie, Position


def _career(seed=1):
    return new_career("Cup", "Leo", "Silva", Position.FW, random.Random(seed))


def test_cup_starts_with_full_bracket_including_the_user():
    state = _career()
    assert state.cup is not None
    first_round = [t for t in state.cup_ties if t.round_size == C.NUM_CUP_TEAMS]
    assert len(first_round) == C.NUM_CUP_TEAMS // 2
    clubs_in = {t.home_club_id for t in first_round} | {t.away_club_id for t in first_round}
    assert state.user_club_id in clubs_in


def test_cup_resolves_to_a_single_champion():
    state = _career(4)
    rng = random.Random(4)
    while state.season.current_week < C.SEASON_END_WEEK:
        advance_week(state, rng)

    assert state.cup.is_complete
    assert state.cup.champion_club_id is not None
    played = [t for t in state.cup_ties if t.is_played]
    # 16 + 8 + 4 + 2 + 1 = 31 ties in a 32-team knockout.
    assert len(played) == C.NUM_CUP_TEAMS - 1
    for tie in played:
        assert tie.winner_club_id in (tie.home_club_id, tie.away_club_id)


def test_winning_the_final_awards_a_cup_honour():
    state = _career(2)
    club = state.user_club
    opponent = next(c for c in state.clubs.values() if c.id != club.id)
    for player in state.squad(club.id):
        for attr in ATTRIBUTE_NAMES:
            setattr(player, attr, 99)
    for player in state.squad(opponent.id):
        for attr in ATTRIBUTE_NAMES:
            setattr(player, attr, 1)

    # Rig a final between the (overwhelming) user and a hopeless opponent.
    state.cup = Cup(name=C.CUP_NAME, round_size=2)
    state.cup_ties = [CupTie(id=state.next_id(), round_size=2,
                             week_number=C.CUP_WEEKS[-1],
                             home_club_id=club.id, away_club_id=opponent.id)]

    _result, _messages = cup.play_cup_week(state, C.CUP_WEEKS[-1], random.Random(1))

    assert state.cup.is_complete
    assert state.cup.champion_club_id == club.id
    assert any("Cup" in h.title for h in state.honours)
