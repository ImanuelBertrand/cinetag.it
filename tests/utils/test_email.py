from unittest.mock import MagicMock, patch

import jwt
import pytest

from app.extensions import db
from app.models.user import User
from app.utils.email import (
    generate_confirmation_token,
    generate_password_reset_token,
    queue_email,
    send_confirmation_email,
    send_email,
    send_password_reset_email,
)


@pytest.fixture
def email_user(app):
    """Create a test user for email tests."""
    with app.app_context():
        user = User(
            name="Email Test User",
            email="emailtest@example.com",
            new_email="new_email@example.com",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        db.session.expunge_all()
        yield db.session.get(User, user_id)
        db.session.rollback()


def test_send_email_success(app, email_user) -> None:
    """Test send_email returns True on success."""
    with app.app_context():
        app.config["MAIL_DEFAULT_SENDER"] = "noreply@example.com"

        with patch("app.utils.email.mail") as mock_mail:
            result = send_email("recipient@example.com", "Test Subject", "Test body")

        assert result is True
        mock_mail.send.assert_called_once()


def test_send_email_with_sender_name(app) -> None:
    """Test send_email uses sender name when configured."""
    with app.app_context():
        app.config["MAIL_DEFAULT_SENDER"] = "noreply@example.com"
        app.config["MAIL_DEFAULT_SENDER_NAME"] = "CineTagIt"

        with patch("app.utils.email.mail") as mock_mail:
            result = send_email("recipient@example.com", "Test Subject", "Test body")

        assert result is True
        # Verify sender contains both name and email
        call_args = mock_mail.send.call_args[0][0]
        assert "CineTagIt" in str(call_args.sender)
        assert "noreply@example.com" in str(call_args.sender)


def test_send_email_with_list_recipients(app) -> None:
    """Test send_email accepts a list of recipients."""
    with app.app_context():
        app.config["MAIL_DEFAULT_SENDER"] = "noreply@example.com"

        with patch("app.utils.email.mail") as mock_mail:
            result = send_email(["a@example.com", "b@example.com"], "Subject", "Body")

        assert result is True
        call_args = mock_mail.send.call_args[0][0]
        assert len(call_args.recipients) == 2


def test_send_email_failure(app) -> None:
    """Test send_email returns False when an exception occurs."""
    with app.app_context():
        app.config["MAIL_DEFAULT_SENDER"] = "noreply@example.com"

        with patch("app.utils.email.mail") as mock_mail:
            mock_mail.send.side_effect = Exception("SMTP error")
            result = send_email("recipient@example.com", "Subject", "Body")

        assert result is False


def test_generate_confirmation_token(app, email_user) -> None:
    """Test generate_confirmation_token creates a valid JWT token."""
    with app.app_context():
        user = db.session.get(User, email_user.id)
        token = generate_confirmation_token(user)

        assert isinstance(token, str)
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        assert payload["confirmation"] == user.id
        assert payload["new_mail"] == user.new_email


def test_send_confirmation_email_no_new_email(app) -> None:
    """Test send_confirmation_email logs error when user has no new_email."""
    with app.app_context():
        user = User(name="No Email User", email="noemail@example.com")
        db.session.add(user)
        db.session.commit()

        with patch("app.utils.email.send_email") as mock_send:
            send_confirmation_email(user)

        # Email should not be sent
        mock_send.assert_not_called()


def test_send_confirmation_email_sends(app, email_user) -> None:
    """Test send_confirmation_email sends an email when user has new_email."""
    with app.app_context():
        app.config["SERVER_NAME"] = "localhost:8000"
        app.config["PREFERRED_URL_SCHEME"] = "http"
        user = db.session.get(User, email_user.id)

        with app.test_request_context():
            with patch("app.utils.email.send_email") as mock_send:
                send_confirmation_email(user)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == user.new_email
        assert "confirm" in call_args[0][1].lower()


def test_generate_password_reset_token(app, email_user) -> None:
    """Test generate_password_reset_token creates a valid JWT with reset claims."""
    with app.app_context():
        user = db.session.get(User, email_user.id)
        token = generate_password_reset_token(user)

        assert isinstance(token, str)
        payload = jwt.decode(token, app.config["SECRET_KEY"], algorithms=["HS256"])
        assert payload["reset_password"] == user.id
        assert "token" in payload
        assert user.password_reset_token is not None


def test_send_password_reset_email(app, email_user) -> None:
    """Test send_password_reset_email sends a reset email."""
    with app.app_context():
        app.config["SERVER_NAME"] = "localhost:8000"
        app.config["PREFERRED_URL_SCHEME"] = "http"
        user = db.session.get(User, email_user.id)

        with app.test_request_context():
            with patch("app.utils.email.send_email") as mock_send:
                send_password_reset_email(user)

        mock_send.assert_called_once()
        call_args = mock_send.call_args
        assert call_args[0][0] == user.email
        assert "password" in call_args[0][1].lower()


def test_queue_email_invalid_type(app, email_user) -> None:
    """Test queue_email raises ValueError for unknown mail type."""
    with app.app_context():
        user = db.session.get(User, email_user.id)

        with pytest.raises(ValueError, match="Unknown mail type"):
            queue_email(user, "unknown_type")
