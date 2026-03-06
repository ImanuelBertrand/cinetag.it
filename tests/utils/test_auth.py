from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt
import pytest

from app.extensions import db
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.models.user import User
from app.utils.auth import (
    _validate_refresh_identity_and_jti,
    create_temporary_user,
    decode_refresh_token,
    generate_new_tokens,
    verify_refresh_token_and_get_identity,
)


def _make_refresh_token(app, user_id: int, jti: str, expired: bool = False) -> str:
    """Helper to generate a JWT refresh token for testing."""
    secret = app.config["JWT_SECRET_KEY"]
    exp = (
        datetime.now(UTC) - timedelta(hours=1)
        if expired
        else datetime.now(UTC) + timedelta(hours=1)
    )
    return jwt.encode(
        {"sub": str(user_id), "jti": jti, "exp": exp},
        secret,
        algorithm="HS256",
    )


def test_decode_refresh_token_valid(app) -> None:
    """Test decode_refresh_token decodes a valid token."""
    with app.app_context():
        token = _make_refresh_token(app, 1, "test-jti")
        payload = decode_refresh_token(token)
        assert payload["sub"] == "1"
        assert payload["jti"] == "test-jti"


def test_decode_refresh_token_invalid_secret(app) -> None:
    """Test decode_refresh_token raises InvalidTokenError with wrong secret."""
    with app.app_context():
        token = jwt.encode(
            {"sub": "1", "jti": "jti"},
            "wrong_secret",
            algorithm="HS256",
        )
        with pytest.raises(jwt.InvalidTokenError):
            decode_refresh_token(token)


def test_validate_refresh_identity_and_jti_no_identity(app) -> None:
    """Test _validate_refresh_identity_and_jti raises when identity is missing."""
    with app.app_context():
        with pytest.raises(jwt.InvalidTokenError, match="missing 'sub' claim"):
            _validate_refresh_identity_and_jti(None, "some-jti")


def test_validate_refresh_identity_and_jti_no_jti(app) -> None:
    """Test _validate_refresh_identity_and_jti raises when jti is missing."""
    with app.app_context():
        with pytest.raises(jwt.InvalidTokenError, match="missing 'jti' claim"):
            _validate_refresh_identity_and_jti("1", None)


def test_validate_refresh_identity_and_jti_not_in_allowlist(app) -> None:
    """Test _validate_refresh_identity_and_jti raises when JTI not in allowlist."""
    with app.app_context():
        with pytest.raises(jwt.InvalidTokenError, match="not allowed"):
            _validate_refresh_identity_and_jti("1", "nonexistent-jti")


def test_validate_refresh_identity_and_jti_valid(app, test_user) -> None:
    """Test _validate_refresh_identity_and_jti returns True for a valid token."""
    with app.app_context():
        user = db.session.get(User, test_user.id)
        jti = "valid-jti-abc"
        expires_at = (datetime.now(UTC) + timedelta(days=1)).timestamp()
        AllowedRefreshToken.add_token(jti, user.id, expires_at)
        db.session.commit()

        result = _validate_refresh_identity_and_jti(str(user.id), jti)
        assert result is True


def test_verify_refresh_token_and_get_identity_valid(app, test_user) -> None:
    """Test verify_refresh_token_and_get_identity with a valid token."""
    with app.app_context():
        user = db.session.get(User, test_user.id)
        jti = "verify-test-jti"
        expires_at = (datetime.now(UTC) + timedelta(days=1)).timestamp()
        AllowedRefreshToken.add_token(jti, user.id, expires_at)
        db.session.commit()

        token = _make_refresh_token(app, user.id, jti)
        result = verify_refresh_token_and_get_identity(token)

        assert result is not None
        user_id, returned_jti = result
        assert user_id == user.id
        assert returned_jti == jti


def test_verify_refresh_token_expired(app, test_user) -> None:
    """Test verify_refresh_token_and_get_identity raises ExpiredSignatureError."""
    with app.app_context():
        user = db.session.get(User, test_user.id)
        jti = "expired-jti"
        token = _make_refresh_token(app, user.id, jti, expired=True)

        with pytest.raises(jwt.ExpiredSignatureError):
            verify_refresh_token_and_get_identity(token)


def test_verify_refresh_token_invalid(app) -> None:
    """Test verify_refresh_token_and_get_identity raises for bad token."""
    with app.app_context():
        with pytest.raises(jwt.InvalidTokenError):
            verify_refresh_token_and_get_identity("this.is.not.a.valid.token")


def test_create_temporary_user(app) -> None:
    """Test create_temporary_user creates a guest user."""
    with app.app_context():
        user = create_temporary_user()
        assert user is not None
        assert user.id is not None
        assert user.email is None
        assert user.password is None


def test_generate_new_tokens(app, test_user) -> None:
    """Test generate_new_tokens creates valid access and refresh tokens."""
    with app.app_context():
        user = db.session.get(User, test_user.id)
        access_token, refresh_token = generate_new_tokens(user.id)

        assert access_token is not None
        assert refresh_token is not None

        # Verify the tokens are valid JWTs
        access_payload = jwt.decode(
            access_token,
            app.config["JWT_SECRET_KEY"],
            algorithms=["HS256"],
        )
        assert access_payload["sub"] == str(user.id)


def test_generate_new_tokens_with_old_jti_revocation(app, test_user) -> None:
    """Test generate_new_tokens revokes old JTI during rotation."""
    with app.app_context():
        user = db.session.get(User, test_user.id)

        # First, generate initial tokens
        _, _ = generate_new_tokens(user.id)

        # Get the JTI that was added
        token_entry = AllowedRefreshToken.query.filter_by(user_id=user.id).first()
        assert token_entry is not None
        old_jti = token_entry.jti

        # Generate new tokens with rotation
        new_access, new_refresh = generate_new_tokens(
            user.id, old_jti_to_revoke=old_jti
        )

        assert new_access is not None
        assert new_refresh is not None

        # Old JTI should be revoked
        assert AllowedRefreshToken.is_token_allowed(old_jti, user.id) is False
