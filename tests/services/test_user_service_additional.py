from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.errors import UserFeedbackError
from app.extensions import bcrypt, db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.user import User
from app.models.user_movie import UserMovie
from app.services.user_service import (
    authenticate_user,
    get_region_flag,
    queue_confirmation_mail,
)


@pytest.fixture
def registered_user(app):
    """Create a registered (non-guest) user."""
    with app.app_context():
        hashed_pw = bcrypt.generate_password_hash("password123").decode("utf-8")
        user = User(
            display_name="Test User",
            email="testuser@example.com",
            password=hashed_pw,
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge_all()
        yield db.session.get(User, user_id)
        db.session.rollback()


def test_authenticate_user_success(app, registered_user) -> None:
    """Test authenticate_user returns user with valid credentials."""
    with app.app_context():
        data = {"email": "testuser@example.com", "password": "password123"}
        user = authenticate_user(data)
        assert user is not None
        assert user.email == "testuser@example.com"


def test_authenticate_user_wrong_password(app, registered_user) -> None:
    """Test authenticate_user raises UserFeedbackError with wrong password."""
    with app.app_context():
        data = {"email": "testuser@example.com", "password": "wrongpassword"}
        with pytest.raises(UserFeedbackError, match="Invalid email or password"):
            authenticate_user(data)


def test_authenticate_user_unknown_email(app) -> None:
    """Test authenticate_user raises UserFeedbackError with unknown email."""
    with app.app_context():
        data = {"email": "unknown@example.com", "password": "anypassword"}
        with pytest.raises(UserFeedbackError, match="Invalid email or password"):
            authenticate_user(data)


def test_get_region_flag_valid(app) -> None:
    """Test get_region_flag returns correct flag emoji for valid region."""
    with app.app_context():
        flag = get_region_flag("US")
        assert flag is not None
        # US flag is 🇺🇸
        assert len(flag) == 2  # Two regional indicator characters

        flag_gb = get_region_flag("GB")
        assert flag_gb is not None


def test_get_region_flag_invalid_length(app) -> None:
    """Test get_region_flag returns None for invalid region length."""
    with app.app_context():
        assert get_region_flag("USA") is None
        assert get_region_flag("U") is None
        assert get_region_flag("") is None


def test_get_region_flag_non_alpha(app) -> None:
    """Test get_region_flag returns None for non-alphabetic region."""
    with app.app_context():
        assert get_region_flag("12") is None
        assert get_region_flag("U1") is None


def test_queue_confirmation_mail_success(app) -> None:
    """Test queue_confirmation_mail queues an email successfully."""
    with app.app_context():
        user = User(display_name="Queued User", new_email="queue@example.com")
        db.session.add(user)
        db.session.commit()

        with patch("app.services.user_service.queue_email") as mock_queue:
            queue_confirmation_mail(user)
            mock_queue.assert_called_once_with(user, "confirm")


def test_queue_confirmation_mail_rate_limit(app) -> None:
    """Test queue_confirmation_mail raises UserFeedbackError when rate limited."""

    with app.app_context():
        user = User(
            display_name="Rate Limited User", new_email="ratelimited@example.com"
        )
        db.session.add(user)
        db.session.commit()

        # Mock SentConfMails.query to return a recent mail with timezone-aware sent_at
        now = datetime.now(UTC)
        mock_mail = MagicMock()
        mock_mail.sent_at = now - timedelta(seconds=10)  # Recent mail

        with (
            patch("app.services.user_service.SentConfMails.query") as mock_sent_query,
        ):
            mock_sent_query.filter.return_value.delete.return_value = 0
            mock_sent_query.filter_by.return_value.all.return_value = [mock_mail]

            with pytest.raises(UserFeedbackError, match="Too many confirmation mails"):
                queue_confirmation_mail(user)


@pytest.fixture
def user_with_movies(app):
    """Create a user with approved movies for event fetching tests."""
    with app.app_context():
        user = User(
            display_name="Event User",
            email="events@example.com",
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()

        today = datetime.now(UTC).date()
        movie = Movie(
            id=6001,
            original_title="Event Movie",
            popularity=10.0,
            original_language="en",
        )
        db.session.add(movie)

        region_info = MovieRegionInfo(
            movie_id=6001,
            region="US",
            release_date=today + timedelta(days=5),
        )
        db.session.add(region_info)

        lang_info = MovieLanguageInfo(
            movie_id=6001,
            language="en",
            title="Event Movie",
            overview="An overview",
        )
        db.session.add(lang_info)

        user_movie = UserMovie(user_id=user.id, movie_id=6001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        user_id = user.id
        db.session.expunge_all()
        yield db.session.get(User, user_id)
        db.session.rollback()


def test_fetch_user_events_no_user(app) -> None:
    """Test fetch_user_events raises ValueError with no user."""
    with app.app_context():
        from app.services.user_service import fetch_user_events

        with pytest.raises(ValueError, match="User not found"):
            fetch_user_events(None)


def test_fetch_user_events_returns_list(app, user_with_movies) -> None:
    """Test fetch_user_events returns a list of events for a user."""
    with app.app_context():
        app.config["SERVER_NAME"] = "localhost:8000"
        app.config["PREFERRED_URL_SCHEME"] = "http"
        user = db.session.get(User, user_with_movies.id)
        from app.services.user_service import fetch_user_events

        with app.test_request_context():
            events = fetch_user_events(user)

        assert isinstance(events, list)
        assert len(events) >= 1
        assert events[0]["title"] == "Event Movie"
        assert "start" in events[0]
        assert "decision" in events[0]
