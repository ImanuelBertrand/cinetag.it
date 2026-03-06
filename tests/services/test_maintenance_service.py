from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.models.user import User
from app.models.user_calendar import UserCalendar
from app.models.user_movie import UserMovie
from app.services.maintenance_service import (
    purge_abandoned_guests,
    purge_inactive_empty_guests_with_tokens,
)


def _create_old_guest(app, days_old: int = 20) -> int:
    """Create a guest user older than the retention window."""
    with app.app_context():
        cutoff = datetime.now(UTC) - timedelta(days=days_old)
        guest = User(name=None, email=None, password=None)
        db.session.add(guest)
        db.session.flush()
        # Manually set timestamps to simulate an old user
        db.session.execute(
            db.text(
                "UPDATE users SET created_at = :ts, updated_at = :ts WHERE id = :id"
            ),
            {"ts": cutoff, "id": guest.id},
        )
        db.session.commit()
        return guest.id


def test_purge_abandoned_guests_dry_run(app) -> None:
    """Test purge_abandoned_guests in dry_run mode does not delete."""
    with app.app_context():
        guest_id = _create_old_guest(app, days_old=20)

        result = purge_abandoned_guests(retention_days=14, dry_run=True)

        assert "to_delete" in result
        assert guest_id in result["ids"]
        # User should still exist
        assert db.session.get(User, guest_id) is not None


def test_purge_abandoned_guests_deletes(app) -> None:
    """Test purge_abandoned_guests deletes old guests when dry_run=False."""
    with app.app_context():
        guest_id = _create_old_guest(app, days_old=20)

        result = purge_abandoned_guests(retention_days=14, dry_run=False)

        assert result["deleted"] >= 1
        assert db.session.get(User, guest_id) is None


def test_purge_abandoned_guests_keeps_new_users(app) -> None:
    """Test purge_abandoned_guests does not delete recently created guests."""
    with app.app_context():
        # Create a recent guest (less than retention_days old)
        recent_guest = User(name=None, email=None, password=None)
        db.session.add(recent_guest)
        db.session.commit()
        recent_id = recent_guest.id

        result = purge_abandoned_guests(retention_days=14, dry_run=True)

        assert recent_id not in result["ids"]


def test_purge_abandoned_guests_keeps_users_with_email(app) -> None:
    """Test purge_abandoned_guests does not delete users with emails."""
    with app.app_context():
        # Create a user with email (not a pure guest)
        user = User(name="Registered", email="registered@example.com")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        result = purge_abandoned_guests(retention_days=14, dry_run=True)

        assert user_id not in result["ids"]


def test_purge_abandoned_guests_keeps_users_with_tokens(app) -> None:
    """Test purge_abandoned_guests does not delete guests with active tokens."""
    with app.app_context():
        guest_id = _create_old_guest(app, days_old=20)
        # Add an allowed refresh token for this guest
        expires_at = (datetime.now(UTC) + timedelta(days=7)).timestamp()
        AllowedRefreshToken.add_token("some-jti", guest_id, expires_at)
        db.session.commit()

        result = purge_abandoned_guests(retention_days=14, dry_run=True)

        assert guest_id not in result["ids"]


def test_purge_inactive_empty_guests_dry_run(app) -> None:
    """Test purge_inactive_empty_guests_with_tokens dry_run mode."""
    with app.app_context():
        guest_id = _create_old_guest(app, days_old=20)

        result = purge_inactive_empty_guests_with_tokens(
            retention_days=14, dry_run=True
        )

        assert "to_delete" in result
        # The guest has no movies or calendars
        assert guest_id in result["ids"]


def test_purge_inactive_empty_guests_deletes(app) -> None:
    """Test purge_inactive_empty_guests_with_tokens deletes old empty guests."""
    with app.app_context():
        guest_id = _create_old_guest(app, days_old=20)

        result = purge_inactive_empty_guests_with_tokens(
            retention_days=14, dry_run=False
        )

        assert result["deleted"] >= 1
        assert db.session.get(User, guest_id) is None


def test_purge_inactive_empty_guests_keeps_users_with_movies(app) -> None:
    """Test purge_inactive_empty_guests_with_tokens keeps guests with user movies."""
    with app.app_context():
        guest_id = _create_old_guest(app, days_old=20)

        # Add a user movie for this guest
        from app.models.movie import Movie

        movie = Movie(
            id=9999,
            original_title="Test",
            popularity=1.0,
            original_language="en",
        )
        db.session.add(movie)
        user_movie = UserMovie(user_id=guest_id, movie_id=9999, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        result = purge_inactive_empty_guests_with_tokens(
            retention_days=14, dry_run=True
        )

        assert guest_id not in result["ids"]


def test_purge_inactive_empty_guests_keeps_users_with_calendars(app) -> None:
    """Test purge_inactive_empty_guests_with_tokens keeps guests with calendars."""
    with app.app_context():
        guest_id = _create_old_guest(app, days_old=20)

        # Add a calendar for this guest
        calendar = UserCalendar(
            user_id=guest_id,
            calendar_type="wanted",
            calendar_hash="test-hash-12345",
        )
        db.session.add(calendar)
        db.session.commit()

        result = purge_inactive_empty_guests_with_tokens(
            retention_days=14, dry_run=True
        )

        assert guest_id not in result["ids"]


def test_purge_inactive_empty_guests_keeps_new_users(app) -> None:
    """Test purge_inactive_empty_guests_with_tokens keeps recently created guests."""
    with app.app_context():
        recent_guest = User(name=None, email=None, password=None)
        db.session.add(recent_guest)
        db.session.commit()
        recent_id = recent_guest.id

        result = purge_inactive_empty_guests_with_tokens(
            retention_days=14, dry_run=True
        )

        assert recent_id not in result["ids"]
