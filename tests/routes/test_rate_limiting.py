"""Regression tests for SEC-7 (rate limiting) and SEC-17 (friend-code
enumeration). The limiter is toggled off by default for the suite (see the
autouse fixture in conftest); these tests flip it on and use a distinct
X-Real-IP each so the per-key counters start fresh and don't leak into other
tests."""

import contextlib
from unittest.mock import patch

import pytest

from app.extensions import bcrypt, db, limiter
from app.models.user import User


@pytest.fixture
def limiting_enabled():
    """Enable the limiter for the duration of a test, then reset it."""
    limiter.enabled = True
    try:
        yield
    finally:
        limiter.enabled = False
        # Drop all counters so the shared in-memory store doesn't bleed into
        # other tests.
        with contextlib.suppress(Exception):
            limiter.reset()


def _headers(ip):
    return {"X-Real-IP": ip}


def test_login_post_is_rate_limited(client, limiting_enabled):
    # login is limited to 10/min on POST; the 11th from one IP is a 429.
    headers = _headers("203.0.113.10")
    statuses = []
    for _ in range(12):
        resp = client.post(
            "/login",
            data={"email": "x@example.com", "password": "wrong"},
            headers=headers,
        )
        statuses.append(resp.status_code)
    assert 429 in statuses


def test_login_get_not_limited(client, limiting_enabled):
    # Browsing the login form (GET) is exempt from the credential-path limit.
    headers = _headers("203.0.113.11")
    statuses = [client.get("/login", headers=headers).status_code for _ in range(15)]
    assert 429 not in statuses


def test_friend_request_is_rate_limited(client, app, limiting_enabled):
    with app.app_context():
        user = User(
            display_name="RL User",
            email="rl_user@example.com",
            password=bcrypt.generate_password_hash("password123").decode("utf-8"),
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    headers = _headers("203.0.113.12")
    with (
        patch("app.routes.friend_api.get_current_user") as mock_user,
        app.app_context(),
    ):
        loaded = db.session.get(User, user_id)
        assert loaded is not None
        mock_user.return_value = loaded
        statuses = []
        for _ in range(12):  # limit is 10/min
            resp = client.post(
                "/api/friends/request",
                json={"friend_code": "ZZZZZZZZ"},
                headers=headers,
            )
            statuses.append(resp.status_code)
    # Once throttled the API returns JSON 429.
    assert 429 in statuses


def test_rate_limit_response_is_json_for_api(client, app, limiting_enabled):
    with app.app_context():
        user = User(
            display_name="RL User2",
            email="rl_user2@example.com",
            password=bcrypt.generate_password_hash("password123").decode("utf-8"),
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    headers = _headers("203.0.113.13")
    with (
        patch("app.routes.friend_api.get_current_user") as mock_user,
        app.app_context(),
    ):
        loaded = db.session.get(User, user_id)
        assert loaded is not None
        mock_user.return_value = loaded
        resp = None
        for _ in range(12):
            resp = client.post(
                "/api/friends/request",
                json={"friend_code": "ZZZZZZZZ"},
                headers=headers,
            )
            if resp.status_code == 429:
                break
        assert resp is not None
        assert resp.status_code == 429
        assert resp.is_json
        assert resp.get_json()["success"] is False


def test_friend_request_unknown_code_looks_like_success(client, app):
    """SEC-17: an unknown friend code returns the same response as a real send,
    so valid codes can't be probed."""
    with app.app_context():
        user = User(
            display_name="Prober",
            email="prober@example.com",
            password=bcrypt.generate_password_hash("password123").decode("utf-8"),
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    with (
        patch("app.routes.friend_api.get_current_user") as mock_user,
        app.app_context(),
    ):
        loaded = db.session.get(User, user_id)
        assert loaded is not None
        mock_user.return_value = loaded
        resp = client.post(
            "/api/friends/request",
            json={"friend_code": "DOES-NOT-EXIST"},
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["success"] is True
        assert data["message"] == "Friend request sent successfully."
