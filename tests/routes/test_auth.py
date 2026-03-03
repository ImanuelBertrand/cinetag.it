from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import jwt

from app.extensions import bcrypt, db
from app.models.user import User


def test_registration_flow(client, app) -> None:
    """Test the full registration flow from anonymous to permanent user."""
    # 1. Accessing home should create an anonymous user
    # (via get_current_user in before_request)
    # In tests, we need to make sure the before_request handlers run.
    # The client.get() does this.
    response = client.get("/")
    assert response.status_code == 200

    # 2. Get the registration page
    response = client.get("/register")
    assert response.status_code == 200
    assert b"Register" in response.data

    # 3. Submit registration form
    # We need to mock queue_email to avoid sending actual emails
    with patch("app.services.user_service.queue_email") as mock_queue:
        # We need to simulate the time passing and JS execution for the security checks
        import time

        registration_data = {
            "name": "New User",
            "email": "newuser@example.com",
            "password": "securepassword123",
            "website": "",  # Honeypot
            "form_rendered_at": str(int(time.time()) - 5),  # 5 seconds ago
            "form_state": "initializing",  # JS challenge
        }
        response = client.post(
            "/register", data=registration_data, follow_redirects=True
        )

        assert response.status_code == 200
        assert b"User registered successfully" in response.data
        mock_queue.assert_called_once()

    # 4. Verify user in DB
    with app.app_context():
        user = User.query.filter_by(new_email="newuser@example.com").first()
        assert user is not None
        assert user.name == "New User"
        assert user.email is None  # Not confirmed yet
        assert bcrypt.check_password_hash(user.password, "securepassword123")


def test_registration_honeypot(client, app) -> None:
    """Test that the honeypot field blocks registration."""
    registration_data = {
        "name": "Bot User",
        "email": "bot@example.com",
        "password": "somepassword",
        "website": "http://evil.com",  # Honeypot filled
    }
    response = client.post("/register", data=registration_data, follow_redirects=True)

    # It should pretend success but not actually
    # create/update a user with these credentials
    assert response.status_code == 200
    assert b"Thanks! Please check your email to confirm." in response.data

    with app.app_context():
        user = User.query.filter_by(new_email="bot@example.com").first()
        assert user is None


def test_login_logout_flow(client, app) -> None:
    """Test login and logout functionality."""
    # 1. Create a user first
    with app.app_context():
        hashed_pw = bcrypt.generate_password_hash("password123").decode("utf-8")
        user = User(name="Login User", email="login@example.com", password=hashed_pw)
        db.session.add(user)
        db.session.commit()

    # 2. Login
    login_data = {"email": "login@example.com", "password": "password123"}
    response = client.post("/login", data=login_data, follow_redirects=True)
    assert response.status_code == 200
    # Should redirect to profile
    assert b"Profile" in response.data or b"login@example.com" in response.data

    # 3. Logout
    response = client.post("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Logged out successfully" in response.data


def test_login_invalid_credentials(client, app) -> None:
    """Test login with wrong credentials."""
    login_data = {"email": "nonexistent@example.com", "password": "wrongpassword"}
    response = client.post("/login", data=login_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_email_confirmation(client, app) -> None:
    """Test the email confirmation process."""
    # 1. Create a user with a new_email
    with app.app_context():
        user = User(name="Confirm User", new_email="confirm@example.com")
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        # Generate token
        token = jwt.encode(
            {
                "confirmation": user_id,
                "new_mail": "confirm@example.com",
                "exp": datetime.now(UTC) + timedelta(hours=24),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

    # 2. Access confirmation route
    response = client.get(f"/confirm-email/{token}", follow_redirects=True)
    assert response.status_code == 200
    assert b"Email confirmed successfully" in response.data

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.email == "confirm@example.com"
        assert user.new_email is None


def test_password_reset_flow(client, app) -> None:
    """Test the password reset flow."""
    # 1. Create a user
    with app.app_context():
        user = User(
            name="Reset User",
            email="reset@example.com",
            password="oldpassword",  # noqa: S106
        )
        user.password_reset_token = "secret-token"  # noqa: S105
        db.session.add(user)
        db.session.commit()
        user_id = user.id

        # Generate JWT token for reset
        token = jwt.encode(
            {
                "reset_password": user_id,
                "token": "secret-token",
                "exp": datetime.now(UTC) + timedelta(hours=24),
            },
            app.config["SECRET_KEY"],
            algorithm="HS256",
        )

    # 2. Reset password
    reset_data = {"new_password": "newsecurepassword123"}
    response = client.post(
        f"/reset-password/{token}", data=reset_data, follow_redirects=True
    )
    assert response.status_code == 200
    assert b"Password reset successfully" in response.data

    # 3. Verify new password works
    login_data = {"email": "reset@example.com", "password": "newsecurepassword123"}
    response = client.post("/login", data=login_data, follow_redirects=True)
    assert response.status_code == 200
    assert b"Profile" in response.data
