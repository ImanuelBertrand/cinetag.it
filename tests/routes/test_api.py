from datetime import UTC, timedelta
from datetime import datetime as dt
from unittest.mock import patch

import pytest

from app.extensions import bcrypt, db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.user import User
from app.models.user_movie import UserMovie


@pytest.fixture
def api_user(app):
    """Create a user and return credentials for API tests."""
    with app.app_context():
        hashed_pw = bcrypt.generate_password_hash("password123").decode("utf-8")
        user = User(
            name="API User",
            email="api_user@example.com",
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


@pytest.fixture
def api_movie(app, api_user):
    """Create a test movie for API tests."""
    with app.app_context():
        today = dt.now(UTC).date()
        movie = Movie(
            id=5001,
            original_title="API Test Movie",
            popularity=10.0,
            original_language="en",
        )
        db.session.add(movie)
        region_info = MovieRegionInfo(
            movie_id=5001,
            region="US",
            release_date=today + timedelta(days=10),
        )
        db.session.add(region_info)
        lang_info = MovieLanguageInfo(
            movie_id=5001,
            language="en",
            title="API Test Movie",
            overview="An overview",
        )
        db.session.add(lang_info)
        db.session.commit()
        yield movie
        db.session.rollback()


def _login(client, email="api_user@example.com", password="password123"):
    """Helper to log in a test user and return the client."""
    client.post("/login", data={"email": email, "password": password})
    return client


def test_review_movie_approve(client, app, api_user, api_movie) -> None:
    """Test POST /user/movies/review approves a movie."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/user/movies/review",
                json={"movie_id": 5001, "decision": "approve"},
                content_type="application/json",
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["decision_status"] == "approve"


def test_review_movie_remove(client, app, api_user, api_movie) -> None:
    """Test POST /user/movies/review removes a movie decision."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        # First add a decision
        user_movie = UserMovie(user_id=user.id, movie_id=5001, decision="approve")
        db.session.add(user_movie)
        db.session.commit()

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/user/movies/review",
                json={"movie_id": 5001, "decision": "remove"},
                content_type="application/json",
            )

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["decision_status"] is None


def test_review_movie_invalid_decision(client, app, api_user) -> None:
    """Test POST /user/movies/review with invalid decision returns 400."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/user/movies/review",
                json={"movie_id": 5001, "decision": "invalid"},
                content_type="application/json",
            )

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data


def test_review_movie_no_user(client, app) -> None:
    """Test POST /user/movies/review returns 404 when no user."""
    with patch("app.routes.api.get_current_user", return_value=None):
        response = client.post(
            "/api/user/movies/review",
            json={"movie_id": 5001, "decision": "approve"},
            content_type="application/json",
        )

    assert response.status_code == 404


def test_get_user_events_no_user(client, app) -> None:
    """Test GET /user/events returns 404 when no user."""
    with patch("app.routes.api.get_current_user", return_value=None):
        response = client.get("/api/user/events?start=2025-01-01&end=2025-12-31")

    assert response.status_code == 404


def test_get_user_events_missing_dates(client, app, api_user) -> None:
    """Test GET /user/events returns 400 when date parameters are missing."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.get("/api/user/events")

    assert response.status_code == 400


def test_get_user_events_success(client, app, api_user) -> None:
    """Test GET /user/events returns events successfully."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.get(
                "/api/user/events?start=2025-01-01T00:00:00&end=2025-12-31T00:00:00"
            )

    assert response.status_code == 200
    assert isinstance(response.get_json(), list)


def test_get_movies_api_no_user(client, app) -> None:
    """Test GET /movies/<filter_mode> works without a user (error handled)."""
    with patch("app.routes.api.get_current_user", return_value=None):
        response = client.get("/api/movies/all")

    # The endpoint handles None user by passing it to get_movies_based_on_filter
    # which should fail gracefully
    data = response.get_json()
    assert data is not None


def test_reset_calendar_hashes_no_user(client, app) -> None:
    """Test POST /calendar/reset-hashes returns error when no user."""
    with patch("app.routes.api.get_current_user", return_value=None):
        response = client.post("/api/calendar/reset-hashes")

    data = response.get_json()
    assert data["success"] is False


def test_reset_calendar_hashes_success(client, app, api_user) -> None:
    """Test POST /calendar/reset-hashes resets calendar hashes."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post("/api/calendar/reset-hashes")

    data = response.get_json()
    assert data["success"] is True


def test_check_push_subscription_no_user(client, app) -> None:
    """Test POST /check-push-subscription returns 401 when no user."""
    with patch("app.routes.api.get_current_user", return_value=None):
        response = client.post(
            "/api/check-push-subscription",
            json={"endpoint": "https://push.example.com/123"},
            content_type="application/json",
        )

    assert response.status_code == 401


def test_check_push_subscription_missing_endpoint(client, app, api_user) -> None:
    """Test POST /check-push-subscription returns 400 when endpoint is missing."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/check-push-subscription",
                json={},
                content_type="application/json",
            )

    assert response.status_code == 400


def test_check_push_subscription_not_found(client, app, api_user) -> None:
    """Test POST /check-push-subscription returns exists=False when no subscription."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/check-push-subscription",
                json={"endpoint": "https://push.example.com/nonexistent"},
                content_type="application/json",
            )

    data = response.get_json()
    assert data["success"] is True
    assert data["exists"] is False


def test_unsubscribe_push_no_user(client, app) -> None:
    """Test POST /unsubscribe returns 401 when no user."""
    with patch("app.routes.api.get_current_user", return_value=None):
        response = client.post(
            "/api/unsubscribe",
            json={"endpoint": "https://push.example.com/123"},
            content_type="application/json",
        )

    assert response.status_code == 401


def test_unsubscribe_push_missing_endpoint(client, app, api_user) -> None:
    """Test POST /unsubscribe returns 400 when endpoint is missing."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/unsubscribe",
                json={},
                content_type="application/json",
            )

    assert response.status_code == 400


def test_unsubscribe_push_not_found(client, app, api_user) -> None:
    """Test POST /unsubscribe returns 404 when subscription not found."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/unsubscribe",
                json={"endpoint": "https://push.example.com/nonexistent"},
                content_type="application/json",
            )

    assert response.status_code == 404


def test_update_push_settings_no_user(client, app) -> None:
    """Test POST /update-push-settings returns 401 when no user."""
    with patch("app.routes.api.get_current_user", return_value=None):
        response = client.post(
            "/api/update-push-settings",
            json={"endpoint": "https://push.example.com/123"},
            content_type="application/json",
        )

    assert response.status_code == 401


def test_update_push_settings_missing_endpoint(client, app, api_user) -> None:
    """Test POST /update-push-settings returns 400 when endpoint is missing."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/update-push-settings",
                json={"days_in_advance": [1, 3]},
                content_type="application/json",
            )

    assert response.status_code == 400


def test_update_push_settings_no_settings(client, app, api_user) -> None:
    """Test POST /update-push-settings returns 400 when no settings provided."""
    with app.app_context():
        user = db.session.get(User, api_user.id)

        with patch("app.routes.api.get_current_user", return_value=user):
            response = client.post(
                "/api/update-push-settings",
                json={"endpoint": "https://push.example.com/123"},
                content_type="application/json",
            )

    assert response.status_code == 400


def test_get_vapid_public_key(client, app) -> None:
    """Test GET /vapid-public-key returns the VAPID public key."""
    with patch(
        "app.routes.api.get_vapid_public_key_for_js", return_value="test-vapid-key"
    ):
        response = client.get("/api/vapid-public-key")

    data = response.get_json()
    assert data["success"] is True
    assert data["publicKey"] == "test-vapid-key"


def test_get_vapid_public_key_error(client, app) -> None:
    """Test GET /vapid-public-key returns 500 when error occurs."""
    with patch(
        "app.routes.api.get_vapid_public_key_for_js",
        side_effect=Exception("VAPID error"),
    ):
        response = client.get("/api/vapid-public-key")

    assert response.status_code == 500
    data = response.get_json()
    assert data["success"] is False
