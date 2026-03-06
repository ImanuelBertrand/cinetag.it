from datetime import UTC, datetime, timedelta

import pytest

from app.extensions import db
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.models.user import User


@pytest.fixture
def test_allowed_refresh_user(app):
    """Create a user for AllowedRefreshToken tests."""
    with app.app_context():
        user = User(display_name="Token Test User", email="token_test@example.com")
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge_all()
        yield db.session.get(User, user_id)
        db.session.rollback()


def test_add_token_and_is_token_allowed(app, test_allowed_refresh_user) -> None:
    """Test adding a token and checking if it is allowed."""
    with app.app_context():
        user = db.session.get(User, test_allowed_refresh_user.id)
        jti = "test-jti-12345"
        expires_at = (datetime.now(UTC) + timedelta(days=1)).timestamp()

        AllowedRefreshToken.add_token(jti, user.id, expires_at)
        db.session.commit()

        assert AllowedRefreshToken.is_token_allowed(jti, user.id) is True


def test_is_token_allowed_returns_false_for_unknown_jti(
    app, test_allowed_refresh_user
) -> None:
    """Test that is_token_allowed returns False for unknown JTI."""
    with app.app_context():
        user = db.session.get(User, test_allowed_refresh_user.id)
        assert AllowedRefreshToken.is_token_allowed("nonexistent-jti", user.id) is False


def test_revoke_token(app, test_allowed_refresh_user) -> None:
    """Test that revoke_token removes a token from the allowlist."""
    with app.app_context():
        user = db.session.get(User, test_allowed_refresh_user.id)
        jti = "revoke-test-jti"
        expires_at = (datetime.now(UTC) + timedelta(days=1)).timestamp()

        AllowedRefreshToken.add_token(jti, user.id, expires_at)
        db.session.commit()

        assert AllowedRefreshToken.is_token_allowed(jti, user.id) is True

        result = AllowedRefreshToken.revoke_token(jti)
        db.session.commit()

        assert result is True
        assert AllowedRefreshToken.is_token_allowed(jti, user.id) is False


def test_revoke_token_returns_false_for_unknown_jti(app) -> None:
    """Test that revoke_token returns False when JTI doesn't exist."""
    with app.app_context():
        result = AllowedRefreshToken.revoke_token("nonexistent-jti")
        assert result is False


def test_revoke_all_for_user(app, test_allowed_refresh_user) -> None:
    """Test that revoke_all_for_user removes all tokens for a user."""
    with app.app_context():
        user = db.session.get(User, test_allowed_refresh_user.id)
        expires_at = (datetime.now(UTC) + timedelta(days=1)).timestamp()

        for i in range(3):
            AllowedRefreshToken.add_token(f"jti-{i}", user.id, expires_at)
        db.session.commit()

        for i in range(3):
            assert AllowedRefreshToken.is_token_allowed(f"jti-{i}", user.id) is True

        result = AllowedRefreshToken.revoke_all_for_user(user.id)
        db.session.commit()

        assert result is True
        for i in range(3):
            assert AllowedRefreshToken.is_token_allowed(f"jti-{i}", user.id) is False


def test_revoke_all_for_user_returns_false_when_no_tokens(
    app, test_allowed_refresh_user
) -> None:
    """Test that revoke_all_for_user returns False when no tokens exist."""
    with app.app_context():
        user = db.session.get(User, test_allowed_refresh_user.id)
        result = AllowedRefreshToken.revoke_all_for_user(user.id)
        assert result is False


def test_cleanup_expired_tokens(app, test_allowed_refresh_user) -> None:
    """Test that cleanup_expired_tokens removes expired tokens."""
    with app.app_context():
        user = db.session.get(User, test_allowed_refresh_user.id)
        expired_at = (datetime.now(UTC) - timedelta(days=1)).timestamp()
        future_at = (datetime.now(UTC) + timedelta(days=1)).timestamp()

        AllowedRefreshToken.add_token("expired-jti", user.id, expired_at)
        AllowedRefreshToken.add_token("valid-jti", user.id, future_at)
        db.session.commit()

        count = AllowedRefreshToken.cleanup_expired_tokens()

        assert count == 1
        assert AllowedRefreshToken.is_token_allowed("expired-jti", user.id) is False
        assert AllowedRefreshToken.is_token_allowed("valid-jti", user.id) is True


def test_add_token_with_missing_fields(app) -> None:
    """Test that add_token does nothing when required fields are missing."""
    with app.app_context():
        initial_count = AllowedRefreshToken.query.count()

        AllowedRefreshToken.add_token("", 1, 1234567890.0)
        AllowedRefreshToken.add_token("jti", 0, 1234567890.0)
        AllowedRefreshToken.add_token("jti", 1, 0.0)
        db.session.commit()

        assert AllowedRefreshToken.query.count() == initial_count


def test_repr(app, test_allowed_refresh_user) -> None:
    """Test the __repr__ method."""
    with app.app_context():
        user = db.session.get(User, test_allowed_refresh_user.id)
        expires_at = (datetime.now(UTC) + timedelta(days=1)).timestamp()

        AllowedRefreshToken.add_token("repr-jti", user.id, expires_at)
        db.session.commit()

        token = AllowedRefreshToken.query.filter_by(jti="repr-jti").first()
        assert "repr-jti" in repr(token)
        assert str(user.id) in repr(token)
