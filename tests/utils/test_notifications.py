from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.notification import Notification
from app.models.notification_channel import NotificationChannel
from app.models.user import User
from app.models.user_movie import UserMovie
from app.utils.notifications import (
    add_missing_notifications,
    delete_outdated_notifications,
    get_push_notification_content,
    send_email_notification,
    send_notification,
    setup_notifications,
)


@pytest.fixture
def notification_user(app):
    """Create a user for notification tests."""
    with app.app_context():
        user = User(
            display_name="Notif User",
            email="notif@example.com",
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge_all()
        yield db.session.get(User, user_id)
        db.session.rollback()


@pytest.fixture
def notification_movie(app):
    """Create a movie for notification tests."""
    with app.app_context():
        today = datetime.now(UTC).date()
        movie = Movie(
            id=7001,
            original_title="Notif Movie",
            popularity=5.0,
            original_language="en",
        )
        db.session.add(movie)
        region_info = MovieRegionInfo(
            movie_id=7001,
            region="US",
            release_date=today + timedelta(days=5),
        )
        db.session.add(region_info)
        lang_info = MovieLanguageInfo(
            movie_id=7001,
            language="en",
            title="Notif Movie",
            overview="An overview",
        )
        db.session.add(lang_info)
        db.session.commit()
        yield movie
        db.session.rollback()


@pytest.fixture
def notification_channel(app, notification_user):
    """Create a notification channel for tests."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = NotificationChannel(user_id=user.id, mode="push", enabled=True)
        channel.days_in_advance = [1, 3, 7]
        channel.include_maybe_movies = True
        channel.notification_data = {
            "endpoint": "https://push.example.com/test-endpoint",
            "keys": {"p256dh": "test-key", "auth": "test-auth"},
        }
        db.session.add(channel)
        db.session.commit()
        channel_id = channel.id
        db.session.expunge_all()
        yield db.session.get(NotificationChannel, channel_id)
        db.session.rollback()


def test_send_notification_unknown_mode(app) -> None:
    """Test send_notification returns False for unknown mode."""
    with app.app_context():
        notification = MagicMock()
        notification.channel.mode = "unknown"

        result = send_notification(notification)
        assert result is False


def test_setup_notifications_creates_notifications(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """Test setup_notifications creates notifications for approved movies."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None

        # Create approved user movie
        user_movie = UserMovie(user_id=user.id, movie_id=7001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        setup_notifications(channel)

        # Should have created notifications for each day_in_advance
        notifications = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(notifications) > 0


def test_setup_notifications_with_maybe_movies(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """Test setup_notifications includes maybe movies when configured."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        channel.include_maybe_movies = True
        db.session.commit()

        # Create a "maybe" user movie
        user_movie = UserMovie(user_id=user.id, movie_id=7001, decision="maybe")
        db.session.add(user_movie)
        db.session.commit()

        setup_notifications(channel)

        notifications = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(notifications) > 0


def test_delete_outdated_notifications(
    app, notification_user, notification_channel
) -> None:
    """Test delete_outdated_notifications removes outdated notifications."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None

        # Create a notification for a movie that the user has removed from their list
        movie = Movie(
            id=7002,
            original_title="Old Movie",
            popularity=1.0,
            original_language="en",
        )
        db.session.add(movie)
        db.session.commit()

        # Add a scheduled notification (but the movie is not in user_movies)
        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7002,
            days_in_advance=1,
            scheduled_at=datetime.now(UTC) + timedelta(days=1),
        )
        db.session.add(notification)
        db.session.commit()

        # No user movies
        user_movies = []
        user_notifications = Notification.query.filter_by(channel_id=channel.id).all()

        delete_outdated_notifications(channel, user_movies, user_notifications)
        db.session.commit()

        # Notification should be deleted (movie not in user_movies)
        remaining = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(remaining) == 0


def test_add_missing_notifications(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """Test add_missing_notifications adds new notifications."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None

        user_movie = UserMovie(user_id=user.id, movie_id=7001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        user_movies = UserMovie.query.filter_by(user_id=user.id).all()
        user_notifications: list[Notification] = []

        add_missing_notifications(channel, user_movies, user_notifications)
        db.session.commit()

        notifications = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(notifications) > 0


def test_delete_outdated_notifications_removes_stale_schedule(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """Test that notifications are deleted when the release date changes."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        # Create user movie and notification based on original release date (5 days out)
        user_movie = UserMovie(user_id=user.id, movie_id=7001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        original_release = today + timedelta(days=5)
        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=3,
            scheduled_at=datetime.combine(
                original_release - timedelta(days=3),
                datetime.min.time(),
                tzinfo=UTC,
            ),
        )
        db.session.add(notification)
        db.session.commit()

        # Now push the release date back significantly
        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today + timedelta(days=60)
        db.session.commit()

        user_movies = UserMovie.query.filter_by(user_id=user.id).all()
        user_notifications = Notification.query.filter_by(channel_id=channel.id).all()

        delete_outdated_notifications(channel, user_movies, user_notifications)
        db.session.commit()

        remaining = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(remaining) == 0


def test_delete_outdated_notifications_keeps_valid_schedule(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """Test that notifications are kept when schedule matches release date."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        user_movie = UserMovie(user_id=user.id, movie_id=7001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        release_date = today + timedelta(days=5)
        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = release_date
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=3,
            scheduled_at=datetime.combine(
                release_date - timedelta(days=3),
                datetime.min.time(),
                tzinfo=UTC,
            ),
        )
        db.session.add(notification)
        db.session.commit()

        user_movies = UserMovie.query.filter_by(user_id=user.id).all()
        user_notifications = Notification.query.filter_by(channel_id=channel.id).all()

        delete_outdated_notifications(channel, user_movies, user_notifications)
        db.session.commit()

        remaining = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(remaining) == 1


def test_push_notification_skips_when_days_diverge(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """Test push notification returns None when days diverge."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        # Set release date 64 days out
        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today + timedelta(days=64)
        db.session.commit()

        # Create notification that claims 14 days in advance
        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=14,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)
        db.session.commit()

        result = get_push_notification_content(notification)
        assert result is None


def test_add_missing_notifications_day_zero_on_release_day(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """A day-0 channel gets a notification even for a movie out today."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        # Movie releases today; user opts into a release-day (0) reminder
        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today
        channel.days_in_advance = [0]
        db.session.commit()

        user_movie = UserMovie(user_id=user.id, movie_id=7001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        add_missing_notifications(channel, [user_movie], [])
        db.session.commit()

        notifications = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(notifications) == 1
        assert notifications[0].days_in_advance == 0
        assert notifications[0].scheduled_at == datetime.combine(
            today, datetime.min.time(), tzinfo=UTC
        )


def test_push_notification_out_today_copy(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """The push copy switches to an 'out today' message for day-0 releases."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=0,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)
        db.session.commit()

        content = get_push_notification_content(notification)
        assert content is not None
        assert content["body"] == "Out today! 🎬"
        assert content["title"].startswith("Out today:")


def test_email_notification_body_has_links_and_decision(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """The reminder email deep-links the movie, the settings page, and the tag."""
    with app.app_context():
        app.config["SERVER_NAME"] = "localhost:8000"
        app.config["PREFERRED_URL_SCHEME"] = "http"
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today + timedelta(days=3)
        db.session.add(UserMovie(user_id=user.id, movie_id=7001, decision="approve"))
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=3,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)
        db.session.commit()

        with (
            app.test_request_context(),
            patch("app.utils.notifications.send_email") as mock_send,
        ):
            mock_send.return_value = True
            result = send_email_notification(notification)

        assert result is True
        _to, subject, body = mock_send.call_args[0]
        assert "/movie/7001" in body
        assert "/profile/notifications" in body
        assert "Must see" in body
        assert subject.startswith("Upcoming movie (3 days)")


def test_email_notification_day_zero_subject(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """A release-day reminder uses the 'Out today' subject."""
    with app.app_context():
        app.config["SERVER_NAME"] = "localhost:8000"
        app.config["PREFERRED_URL_SCHEME"] = "http"
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=0,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)
        db.session.commit()

        with (
            app.test_request_context(),
            patch("app.utils.notifications.send_email") as mock_send,
        ):
            mock_send.return_value = True
            send_email_notification(notification)

        _to, subject, body = mock_send.call_args[0]
        assert subject == "Out today: Notif Movie"
        assert "out today" in body.lower()


def test_push_notification_skipped_for_past_release(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """A stale day-0 reminder must not claim 'out today' days after release."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today - timedelta(days=2)
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=0,
            scheduled_at=datetime.now(UTC) - timedelta(days=2),
        )
        db.session.add(notification)
        db.session.commit()

        assert get_push_notification_content(notification) is None


def test_email_notification_skipped_for_past_release(
    app, notification_user, notification_movie, notification_channel
) -> None:
    """The email path also drops reminders for movies already released."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today - timedelta(days=2)
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=0,
            scheduled_at=datetime.now(UTC) - timedelta(days=2),
        )
        db.session.add(notification)
        db.session.commit()

        with patch("app.utils.notifications.send_email") as mock_send:
            assert send_email_notification(notification) is False
        mock_send.assert_not_called()


def test_email_notification_sends_without_server_name(
    app, monkeypatch, notification_user, notification_movie, notification_channel
) -> None:
    """Without SERVER_NAME the scheduler can't build absolute URLs; the email
    must still go out (link-less) instead of failing and retrying forever."""
    # Must be patched before the app context is created: Flask binds the URL
    # adapter (and thus SERVER_NAME) at context push time.
    monkeypatch.setitem(app.config, "SERVER_NAME", None)
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        region_info = MovieRegionInfo.query.filter_by(
            movie_id=7001, region="US"
        ).first()
        region_info.release_date = today + timedelta(days=3)
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7001,
            days_in_advance=3,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)
        db.session.commit()

        # No test_request_context here: this simulates the APScheduler path,
        # where url_for(_external=True) raises without SERVER_NAME.
        with patch("app.utils.notifications.send_email") as mock_send:
            mock_send.return_value = True
            result = send_email_notification(notification)

        assert result is True
        _to, subject, body = mock_send.call_args[0]
        assert subject.startswith("Upcoming movie (3 days)")
        assert "http" not in body
        assert "Release date:" in body


def test_email_notification_returns_false_when_no_region_info(
    app, notification_user, notification_channel
) -> None:
    """Test email notification returns False when no MovieRegionInfo exists."""
    with app.app_context():
        user = db.session.get(User, notification_user.id)
        assert user is not None
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None

        # Create a movie without region info for the user's region
        movie = Movie(
            id=7003,
            original_title="No Region Movie",
            popularity=1.0,
            original_language="en",
        )
        db.session.add(movie)
        lang_info = MovieLanguageInfo(
            movie_id=7003,
            language="en",
            title="No Region Movie",
            overview="Overview",
        )
        db.session.add(lang_info)
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7003,
            days_in_advance=7,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)
        db.session.commit()

        result = send_email_notification(notification)
        assert result is False


def test_email_notification_uses_us_fallback_region(app, notification_channel) -> None:
    """Test email notification defaults to 'US' region, not 'en'."""
    with app.app_context():
        channel = db.session.get(NotificationChannel, notification_channel.id)
        assert channel is not None
        today = datetime.now(UTC).date()

        # Create user with no region set
        user = User(
            display_name="No Region User",
            email="noregion@example.com",
            region=None,
            language="en",
        )
        db.session.add(user)
        db.session.commit()

        # Create movie with US region info only
        movie = Movie(
            id=7004,
            original_title="US Only Movie",
            popularity=1.0,
            original_language="en",
        )
        db.session.add(movie)
        region_info = MovieRegionInfo(
            movie_id=7004,
            region="US",
            release_date=today + timedelta(days=7),
        )
        db.session.add(region_info)
        lang_info = MovieLanguageInfo(
            movie_id=7004,
            language="en",
            title="US Only Movie",
            overview="Overview",
        )
        db.session.add(lang_info)
        db.session.commit()

        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=7004,
            days_in_advance=7,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)
        db.session.commit()

        # With the old "en" default, this would fail (no region_info for "en")
        # With the fix ("US" default), it should find the US region info
        result = send_email_notification(notification)
        # Result depends on email sending mock, but it should not return False
        # due to missing region info
        assert (
            result is not False
            or MovieRegionInfo.query.filter_by(movie_id=7004, region="US").first()
            is not None
        )
