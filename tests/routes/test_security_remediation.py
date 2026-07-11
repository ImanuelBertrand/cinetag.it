"""Regression tests for the security remediation (SECURITY_REMEDIATION.md)."""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest

from app.errors import UserFeedbackError
from app.extensions import bcrypt, db
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.models.movie import Movie
from app.models.notification_channel import NotificationChannel
from app.models.send_confirmation_mails import SentConfirmationMails
from app.models.user import User
from app.services.user_service import (
    authenticate_user,
    queue_confirmation_mail,
    reset_user_password,
)
from app.utils.auth import generate_new_tokens
from app.utils.email import generate_password_reset_token
from app.utils.webpush import validate_push_endpoint


def _user(user_id: int) -> User:
    """Load a user, asserting it exists (keeps the type checker happy)."""
    user = db.session.get(User, user_id)
    assert user is not None
    return user


@pytest.fixture
def pw_user(app):
    """A registered user with a known password. Yields its id."""
    with app.app_context():
        user = User(
            display_name="PW User",
            email="pw_user@example.com",
            password=bcrypt.generate_password_hash("password123").decode("utf-8"),
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge_all()
        yield user_id
        db.session.rollback()


# --- SEC-1: display_name validation (server-side defence-in-depth) ---


def test_display_name_control_chars_rejected(client, app, test_user):
    user_id = test_user.id
    with patch("app.routes.html.get_current_user") as mock_user, app.app_context():
        user = _user(user_id)
        mock_user.return_value = user
        original = user.display_name
        client.post(
            "/profile",
            data={
                "display_name": "bad\x00name",
                "language": "en",
                "region": "US",
                "email": user.email,
            },
            follow_redirects=True,
        )
        db.session.expire_all()
        assert _user(user_id).display_name == original


def test_display_name_too_long_rejected(client, app, test_user):
    user_id = test_user.id
    with patch("app.routes.html.get_current_user") as mock_user, app.app_context():
        user = _user(user_id)
        mock_user.return_value = user
        original = user.display_name
        client.post(
            "/profile",
            data={
                "display_name": "x" * 101,
                "language": "en",
                "region": "US",
                "email": user.email,
            },
            follow_redirects=True,
        )
        db.session.expire_all()
        assert _user(user_id).display_name == original


# --- SEC-2 / SEC-3: password reset validation + session revocation ---


def test_reset_password_rejects_short_password(app, pw_user):
    with app.app_context():
        token = generate_password_reset_token(_user(pw_user))
        with pytest.raises(UserFeedbackError):
            reset_user_password(token, "short")
        token = generate_password_reset_token(_user(pw_user))
        with pytest.raises(UserFeedbackError):
            reset_user_password(token, "")


def test_reset_password_revokes_all_tokens(app, pw_user):
    with app.app_context():
        exp = (datetime.now(UTC) + timedelta(days=7)).timestamp()
        AllowedRefreshToken.add_token("jti-reset-1", pw_user, exp)
        db.session.commit()
        assert AllowedRefreshToken.is_token_allowed("jti-reset-1", pw_user)

        token = generate_password_reset_token(_user(pw_user))
        reset_user_password(token, "newvalidpassword")

        assert not AllowedRefreshToken.is_token_allowed("jti-reset-1", pw_user)


def test_logout_revokes_tokens(client, app, pw_user):
    with patch("app.routes.html.get_current_user") as mock_user, app.app_context():
        mock_user.return_value = _user(pw_user)
        exp = (datetime.now(UTC) + timedelta(days=7)).timestamp()
        AllowedRefreshToken.add_token("jti-logout-1", pw_user, exp)
        db.session.commit()

        client.post("/logout", follow_redirects=True)

        db.session.expire_all()
        assert not AllowedRefreshToken.is_token_allowed("jti-logout-1", pw_user)


# --- SEC-14: refresh-token rotation is the atomic gate ---


def test_token_rotation_refuses_reused_jti(app, pw_user):
    with app.app_context():
        exp = (datetime.now(UTC) + timedelta(days=7)).timestamp()
        AllowedRefreshToken.add_token("jti-rotate", pw_user, exp)
        db.session.commit()

        access, refresh = generate_new_tokens(pw_user, "jti-rotate")
        assert access is not None
        assert refresh is not None
        assert not AllowedRefreshToken.is_token_allowed("jti-rotate", pw_user)

        # Replaying the now-revoked jti must not mint a second successor.
        access2, refresh2 = generate_new_tokens(pw_user, "jti-rotate")
        assert access2 is None
        assert refresh2 is None


# --- SEC-5 / SEC-9: push endpoint validation + allowlist ---


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://push.example.com/x",  # not https
        "https://169.254.169.254/latest/meta-data",  # cloud metadata (link-local)
        "https://127.0.0.1/x",  # loopback
        "https://10.1.2.3/x",  # private
        "ftp://push.example.com/x",  # wrong scheme
    ],
)
def test_validate_push_endpoint_rejects_unsafe(endpoint):
    with pytest.raises(UserFeedbackError):
        validate_push_endpoint(endpoint)


def test_validate_push_endpoint_allows_public_https():
    # A public IP literal avoids a real DNS lookup while exercising the check.
    validate_push_endpoint("https://8.8.8.8/push/abc")


def test_subscribe_rejects_private_endpoint(client, app, pw_user):
    with patch("app.routes.api.get_current_user") as mock_user, app.app_context():
        mock_user.return_value = _user(pw_user)
        resp = client.post(
            "/api/subscribe",
            json={"endpoint": "https://127.0.0.1/x", "keys": {"a": "b"}},
        )
        assert resp.status_code == 400


def test_subscribe_strips_unknown_keys(client, app, pw_user):
    with patch("app.routes.api.get_current_user") as mock_user, app.app_context():
        mock_user.return_value = _user(pw_user)
        resp = client.post(
            "/api/subscribe",
            json={
                "endpoint": "https://8.8.8.8/push/abc",
                "keys": {"p256dh": "k", "auth": "a"},
                "disabled_reason": "injected",  # must not be persisted
                "is_admin": True,
            },
        )
        assert resp.status_code == 200
        db.session.expire_all()
        channel = NotificationChannel.query.filter_by(
            user_id=pw_user, mode="push"
        ).first()
        assert channel is not None
        assert set(channel.notification_data.keys()) == {
            "endpoint",
            "keys",
            "user_agent",
        }
        assert "disabled_reason" not in channel.notification_data
        assert "is_admin" not in channel.notification_data


# --- SEC-8: account enumeration ---


def test_login_unknown_email_does_not_crash(app):
    """The missing-user branch runs a dummy bcrypt compare and reports the same
    generic error as a wrong password (no fast-path leak)."""
    with app.app_context(), pytest.raises(UserFeedbackError):
        authenticate_user({"email": "nobody@example.com", "password": "whatever"})


def test_profile_email_change_enumeration_is_neutral(client, app, pw_user):
    with app.app_context():
        other = User(
            email="taken@example.com",
            password=bcrypt.generate_password_hash("password123").decode("utf-8"),
            region="US",
            language="en",
        )
        db.session.add(other)
        db.session.commit()

    with patch("app.routes.html.get_current_user") as mock_user, app.app_context():
        user = _user(pw_user)
        mock_user.return_value = user
        resp = client.post(
            "/profile",
            data={
                "display_name": user.display_name or "",
                "language": "en",
                "region": "US",
                "email": "taken@example.com",
                "current_password": "password123",
            },
            follow_redirects=True,
        )
        assert b"already in use" not in resp.data
        db.session.expire_all()
        assert _user(pw_user).new_email != "taken@example.com"


# --- SEC-16: per-account confirmation-mail rate limit ---


def test_confirmation_mail_per_account_limit(app, pw_user):
    with app.app_context(), patch("app.services.user_service.queue_email"):
        user = _user(pw_user)
        now = datetime.now(UTC)
        for i in range(5):
            db.session.add(
                SentConfirmationMails(
                    email=f"victim{i}@example.com", user_id=user.id, sent_at=now
                )
            )
        db.session.commit()
        user.new_email = "victim-new@example.com"
        with pytest.raises(UserFeedbackError):
            queue_confirmation_mail(user)


# --- SEC-15: input validation returns 4xx not 500 ---


def test_review_movie_bad_id(client, app, pw_user):
    with patch("app.routes.api.get_current_user") as mock_user, app.app_context():
        mock_user.return_value = _user(pw_user)
        resp = client.post(
            "/api/user/movies/review",
            json={"movie_id": "not-an-int", "decision": "approve"},
        )
        assert resp.status_code == 400


def test_review_movie_missing_movie(client, app, pw_user):
    with patch("app.routes.api.get_current_user") as mock_user, app.app_context():
        mock_user.return_value = _user(pw_user)
        resp = client.post(
            "/api/user/movies/review",
            json={"movie_id": 999999999, "decision": "approve"},
        )
        assert resp.status_code == 404


def test_user_events_bad_date(client, app, pw_user):
    with patch("app.routes.api.get_current_user") as mock_user, app.app_context():
        mock_user.return_value = _user(pw_user)
        resp = client.get("/api/user/events?start=not-a-date&end=also-bad")
        assert resp.status_code == 400


# --- SEC-13: poster filename allowlist ---


def test_poster_bad_extension_rejected(client):
    resp = client.get("/poster/500/notanimage.txt")
    assert resp.status_code == 400


def test_poster_valid_width_bad_name(client):
    resp = client.get("/poster/500/....jpgx")
    assert resp.status_code == 400


def test_review_movie_valid(client, app, pw_user):
    with app.app_context():
        movie = Movie(id=4242, original_title="X", original_language="en")
        db.session.add(movie)
        db.session.commit()
        movie_id = movie.id

    with patch("app.routes.api.get_current_user") as mock_user, app.app_context():
        mock_user.return_value = _user(pw_user)
        resp = client.post(
            "/api/user/movies/review",
            json={"movie_id": movie_id, "decision": "approve"},
        )
        assert resp.status_code == 201
        assert resp.get_json()["decision_status"] == "approve"
