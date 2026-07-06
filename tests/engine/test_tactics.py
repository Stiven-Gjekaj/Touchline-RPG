"""Tests for sub-positions, formations, and mentality effects."""

from __future__ import annotations

import random

from touchline.engine import constants as C
from touchline.engine import simulation as sim
from touchline.engine.career import new_career, set_tactic
from touchline.engine.models import Match, Mentality, Position


def _career(seed=1):
    return new_career("T", "Leo", "Silva", Position.FW, random.Random(seed))


def test_generated_players_have_consistent_sub_positions():
    state = _career()
    for player in state.players.values():
        assert player.sub_position is not None
        assert C.SUB_POSITION_TO_BROAD[player.sub_position] == player.position


def test_set_tactic_validates_input():
    state = _career()
    set_tactic(state, "4-3-3", "ATTACKING")
    assert state.tactic.formation == "4-3-3"
    assert state.tactic.mentality == Mentality.ATTACKING

    set_tactic(state, "9-9-9", "NONSENSE")  # ignored
    assert state.tactic.formation == "4-3-3"
    assert state.tactic.mentality == Mentality.ATTACKING


def test_formation_changes_starting_xi_shape():
    state = _career(2)
    squad = state.squad(state.user_club.id)

    xi_433 = sim.select_starting_xi(squad, formation=C.FORMATIONS["4-3-3"])
    xi_532 = sim.select_starting_xi(squad, formation=C.FORMATIONS["5-3-2"])

    assert len(xi_433) == len(xi_532) == 11
    assert sum(1 for p in xi_433 if p.position == Position.FW) == 3
    assert sum(1 for p in xi_532 if p.position == Position.DF) == 5


def test_attacking_mentality_scores_and_concedes_more_than_defensive():
    state = _career(5)
    club = state.user_club
    opponent = next(c for c in state.clubs_in_league(club.league_id) if c.id != club.id)

    def averages(mentality: str, trials: int = 300) -> tuple[float, float]:
        set_tactic(state, "4-4-2", mentality)
        rng = random.Random(1)
        goals_for = goals_against = 0
        for _ in range(trials):
            for p in state.players.values():
                p.injury_weeks_remaining = 0
                p.condition = 100
            match = Match(id=state.next_id(), season_id=state.season.id,
                          week_number=1, home_club_id=club.id,
                          away_club_id=opponent.id)
            state.matches[match.id] = match
            result = sim.simulate_match(state, match, rng)
            goals_for += result.home_goals
            goals_against += result.away_goals
        return goals_for / trials, goals_against / trials

    atk_for, atk_against = averages("ATTACKING")
    def_for, def_against = averages("DEFENSIVE")

    assert atk_for > def_for            # attacking scores more
    assert atk_against > def_against    # but concedes more
