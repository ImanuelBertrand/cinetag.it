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
    send_notification,
    setup_notifications,
)


@pytest.fixture
def notification_user(app):
    """Create a user for notification tests."""
    with app.app_context():
        user = User(
            name="Notif User",
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
        channel = db.session.get(NotificationChannel, notification_channel.id)

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
        channel = db.session.get(NotificationChannel, notification_channel.id)
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
        channel = db.session.get(NotificationChannel, notification_channel.id)

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
        channel = db.session.get(NotificationChannel, notification_channel.id)

        user_movie = UserMovie(user_id=user.id, movie_id=7001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        user_movies = UserMovie.query.filter_by(user_id=user.id).all()
        user_notifications: list[Notification] = []

        add_missing_notifications(channel, user_movies, user_notifications)
        db.session.commit()

        notifications = Notification.query.filter_by(channel_id=channel.id).all()
        assert len(notifications) > 0
