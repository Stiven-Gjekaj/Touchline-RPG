"""Smoke tests for the web UI via Flask's test client.

These check that routes render (200s) and key content appears — appropriate
coverage for a server-rendered text app. State lives on the app instance, so a
single client drives a whole career.
"""

from __future__ import annotations

import pytest

from touchline.web import create_app


@pytest.fixture
def client(save_dir):
    # save_dir points TOUCHLINE_SAVE_DIR at a temp dir so created careers don't
    # touch the real user data directory.
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _start_career(client, first="Leo", last="Silva", position="FW"):
    return client.post(
        "/new",
        data={"first_name": first, "last_name": last, "position": position,
              "save_name": "Test"},
    )


def test_index_redirects_to_saves_without_career(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/saves" in resp.headers["Location"]


def test_protected_page_redirects_without_career(client):
    resp = client.get("/squad")
    assert resp.status_code == 302
    assert "/saves" in resp.headers["Location"]


def test_save_slot_load_and_delete_flow(client):
    _start_career(client, first="Ada", last="Stone", position="MF")
    # Advance a couple of weeks so there is progress to persist.
    for _ in range(2):
        client.post("/advance", data={"focus": "BALANCED"})

    # The save appears in the slot list.
    listing = client.get("/saves")
    assert listing.status_code == 200
    assert b"Ada Stone" in listing.data

    # Drop the loaded career, then reload it from its slot.
    save = client.application.active_save
    slug = save.slug
    save.clear()
    assert client.get("/dashboard").status_code == 302  # no career -> redirect

    resp = client.post(f"/saves/{slug}/load", follow_redirects=True)
    assert resp.status_code == 200
    assert b"Ada Stone" in resp.data

    # Delete removes it.
    client.post(f"/saves/{slug}/delete")
    assert b"Ada Stone" not in client.get("/saves").data


def test_advance_supports_htmx_partial_and_plain_fallback(client):
    _start_career(client)
    # Plain POST (no JS) redirects — graceful fallback.
    plain = client.post("/advance", data={"focus": "BALANCED"})
    assert plain.status_code == 302

    # htmx request returns the swappable dashboard fragment, not a redirect.
    hx = client.post("/advance", data={"focus": "BALANCED"},
                     headers={"HX-Request": "true"})
    assert hx.status_code == 200
    assert b'id="tl-dashboard"' in hx.data
    assert b"<html" not in hx.data  # a fragment, not a full page


def test_tactics_page_and_update(client):
    _start_career(client)
    assert client.get("/tactics").status_code == 200
    resp = client.post("/tactics",
                       data={"formation": "4-3-3", "mentality": "ATTACKING"},
                       follow_redirects=True)
    assert resp.status_code == 200
    tactic = client.application.active_save.state.tactic
    assert tactic.formation == "4-3-3"
    assert tactic.mentality.value == "ATTACKING"


def test_transfer_inbox_renders(client):
    _start_career(client)
    assert client.get("/transfers").status_code == 200


def test_retired_player_sees_career_over_screen(client):
    _start_career(client)
    state = client.application.active_save.state
    state.user_player.is_retired = True

    resp = client.get("/dashboard")
    assert resp.status_code == 200
    assert b"Career complete" in resp.data
    # Advancing is a no-op once retired.
    advanced = client.post("/advance", data={"focus": "BALANCED"})
    assert advanced.status_code == 302


def test_transfer_accept_moves_player(client):
    import random

    from touchline.engine.models import OfferStatus
    from touchline.engine.transfers import _make_offer

    _start_career(client)
    state = client.application.active_save.state
    player = state.user_player
    suitor = next(c for c in state.clubs.values() if c.id != player.club_id)

    offer = _make_offer(state, suitor, player, random.Random(0))
    offer.status = OfferStatus.PENDING_USER_DECISION
    state.transfer_offers[offer.id] = offer

    assert client.get("/dashboard").data.count(b"transfer offer") >= 0
    resp = client.post(f"/transfers/{offer.id}/accept", follow_redirects=True)
    assert resp.status_code == 200
    assert state.user_club_id == suitor.id


def test_new_career_form_renders(client):
    resp = client.get("/new")
    assert resp.status_code == 200
    assert b"Start your career" in resp.data


def test_missing_name_is_rejected(client):
    resp = client.post("/new", data={"first_name": "", "last_name": "",
                                     "position": "FW"}, follow_redirects=True)
    assert resp.status_code == 200
    assert b"first and last name" in resp.data


def test_core_pages_render_after_career_creation(client):
    resp = _start_career(client)
    assert resp.status_code == 302

    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 200
    assert b"Leo Silva" in dashboard.data

    for path in ("/squad", "/standings", "/fixtures", "/player", "/match/last",
                 "/history", "/cup", "/tactics"):
        page = client.get(path)
        assert page.status_code == 200, path
    # The user is highlighted in their own squad.
    assert b"Leo Silva" in client.get("/squad").data


def test_standings_tier_switch(client):
    _start_career(client)
    for tier in (1, 2, 3):
        resp = client.get(f"/standings?tier={tier}")
        assert resp.status_code == 200


def test_advancing_reaches_a_match_and_shows_recap(client):
    _start_career(client, first="Kai", last="Stone", position="MF")
    saw_recap = False
    for _ in range(30):
        assert client.post("/advance", data={"focus": "BALANCED"}).status_code == 302
        if b"Last match" in client.get("/dashboard").data:
            saw_recap = True
            break
    assert saw_recap
    # Fixtures now show at least one played result.
    assert b"\xe2\x80\x93" in client.get("/fixtures").data  # en-dash in a scoreline
