from unittest.mock import patch

from app.extensions import db
from app.models.notification_channel import NotificationChannel
from app.models.user import User


def _user(email):
    user = User(display_name=email, email=email, region="US", language="en")
    db.session.add(user)
    db.session.commit()
    return user


def _push_channel(user, endpoint, enabled=True, extra=None):
    channel = NotificationChannel(user_id=user.id, mode="push", enabled=enabled)
    channel.days_in_advance = [1, 3, 7]
    channel.include_maybe_movies = True
    channel.notification_data = {"endpoint": endpoint, **(extra or {})}
    db.session.add(channel)
    db.session.commit()
    return channel


def test_list_channels_only_returns_own(client, app) -> None:
    """The channel list is scoped to the current user."""
    with app.app_context():
        me = _user("me@example.com")
        other = _user("other@example.com")
        email_channel = NotificationChannel(user_id=me.id, mode="email", enabled=True)
        email_channel.days_in_advance = [3]
        db.session.add(email_channel)
        _push_channel(me, "https://push/me")
        _push_channel(other, "https://push/other")
        db.session.commit()

        with patch("app.routes.api.get_current_user", return_value=me):
            response = client.get("/api/notification-channels")

        data = response.get_json()
        assert data["success"] is True
        modes = sorted(c["mode"] for c in data["channels"])
        assert modes == ["email", "push"]  # exactly my two channels


def test_current_device_flagged_and_labeled(client, app) -> None:
    """A push channel is flagged as the current device and labeled from its UA."""
    with app.app_context():
        me = _user("dev@example.com")
        _push_channel(
            me,
            "https://push/this",
            extra={
                "user_agent": (
                    "Mozilla/5.0 (Windows NT 10.0) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120 Safari/537.36"
                )
            },
        )

        with patch("app.routes.api.get_current_user", return_value=me):
            response = client.get(
                "/api/notification-channels?endpoint=https://push/this"
            )

        channel = response.get_json()["channels"][0]
        assert channel["is_current_device"] is True
        assert channel["device_label"] == "Chrome on Windows"


def test_update_channel_rejects_other_owner(client, app) -> None:
    """A user cannot update another user's channel."""
    with app.app_context():
        me = _user("a@example.com")
        other = _user("b@example.com")
        their_channel = _push_channel(other, "https://push/theirs")

        with patch("app.routes.api.get_current_user", return_value=me):
            response = client.post(
                f"/api/notification-channels/{their_channel.id}",
                json={"enabled": False},
            )

        assert response.status_code == 404
        db.session.expire_all()
        unchanged = db.session.get(NotificationChannel, their_channel.id)
        assert unchanged is not None
        assert unchanged.enabled is True


def test_update_channel_updates_fields(client, app) -> None:
    """Updating a channel persists enabled/days/include_maybe."""
    with app.app_context():
        me = _user("c@example.com")
        channel = _push_channel(me, "https://push/mine")

        with patch("app.routes.api.get_current_user", return_value=me):
            response = client.post(
                f"/api/notification-channels/{channel.id}",
                json={
                    "enabled": False,
                    "days_in_advance": [0, 2],
                    "include_maybe_movies": False,
                },
            )

        assert response.status_code == 200
        db.session.expire_all()
        updated = db.session.get(NotificationChannel, channel.id)
        assert updated is not None
        assert updated.enabled is False
        assert updated.days_in_advance == [0, 2]
        assert updated.include_maybe_movies is False


def test_update_channel_coerces_string_days(client, app) -> None:
    """String day values are coerced to ints — a stored str would break the
    (movie_id, day) notification dedup key and re-send reminders hourly."""
    with app.app_context():
        me = _user("e@example.com")
        channel = _push_channel(me, "https://push/strings")

        with patch("app.routes.api.get_current_user", return_value=me):
            response = client.post(
                f"/api/notification-channels/{channel.id}",
                json={"days_in_advance": ["2", 7, "junk", -1]},
            )

        assert response.status_code == 200
        db.session.expire_all()
        updated = db.session.get(NotificationChannel, channel.id)
        assert updated is not None
        assert updated.days_in_advance == [2, 7]


def test_update_channel_rejects_non_list_days(client, app) -> None:
    """A days_in_advance value that is not a list is a 400, not silent defaults."""
    with app.app_context():
        me = _user("f@example.com")
        channel = _push_channel(me, "https://push/badtype")

        with patch("app.routes.api.get_current_user", return_value=me):
            response = client.post(
                f"/api/notification-channels/{channel.id}",
                json={"days_in_advance": 3},
            )

        assert response.status_code == 400
        db.session.expire_all()
        unchanged = db.session.get(NotificationChannel, channel.id)
        assert unchanged is not None
        assert unchanged.days_in_advance == [1, 3, 7]


def test_list_channels_normalizes_legacy_days(client, app) -> None:
    """Legacy rows storing days as a JSON string or with string elements are
    normalized to a list of ints so the settings page doesn't crash."""
    with app.app_context():
        me = _user("g@example.com")
        channel = _push_channel(me, "https://push/legacy")
        channel.days_in_advance = '[1, "3", 7]'
        db.session.add(channel)
        db.session.commit()

        with patch("app.routes.api.get_current_user", return_value=me):
            response = client.get("/api/notification-channels")

        listed = response.get_json()["channels"][0]
        assert listed["days_in_advance"] == [1, 3, 7]


def test_expired_flag_roundtrip(client, app) -> None:
    """An expiry-disabled channel reports it, and re-enabling clears the flag."""
    with app.app_context():
        me = _user("d@example.com")
        channel = _push_channel(
            me,
            "https://push/expired",
            enabled=False,
            extra={"disabled_reason": "expired"},
        )

        with patch("app.routes.api.get_current_user", return_value=me):
            listed = client.get("/api/notification-channels").get_json()
            assert listed["channels"][0]["disabled_reason"] == "expired"

            client.post(
                f"/api/notification-channels/{channel.id}",
                json={"enabled": True},
            )
            relisted = client.get("/api/notification-channels").get_json()

        assert relisted["channels"][0]["disabled_reason"] is None
        db.session.expire_all()
        reenabled = db.session.get(NotificationChannel, channel.id)
        assert reenabled is not None
        assert reenabled.enabled is True
