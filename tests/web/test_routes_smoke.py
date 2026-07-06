"""Smoke tests for the web UI via Flask's test client.

These check that routes render (200s) and key content appears — appropriate
coverage for a server-rendered text app. State lives on the app instance, so a
single client drives a whole career.
"""

from __future__ import annotations

import pytest

from touchline.web import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config.update(TESTING=True)
    return app.test_client()


def _start_career(client, first="Leo", last="Silva", position="FW"):
    return client.post(
        "/new",
        data={"first_name": first, "last_name": last, "position": position,
              "save_name": "Test"},
    )


def test_index_redirects_to_new_without_career(client):
    resp = client.get("/")
    assert resp.status_code == 302
    assert "/new" in resp.headers["Location"]


def test_protected_page_redirects_without_career(client):
    resp = client.get("/squad")
    assert resp.status_code == 302
    assert "/new" in resp.headers["Location"]


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

    for path in ("/squad", "/standings", "/fixtures", "/player", "/match/last"):
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
