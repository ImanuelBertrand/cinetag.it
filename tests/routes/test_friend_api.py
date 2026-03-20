from unittest.mock import patch

import pytest

from app.extensions import db
from app.models.friendship import Friendship
from app.models.user import User


@pytest.fixture
def authenticated_client(client, app):
    """A test client with an authenticated user."""
    with app.app_context():
        user = User(
            display_name="Auth User",
            email="auth@example.com",
            password="password",  # noqa: S106
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    # We can mock g.current_user if the API uses get_current_user()
    # But since it's a request-based app, we might need to mock the authentication.
    # A simpler way for these tests is to patch 'get_current_user'
    # or to actually set up the JWT cookies.
    # Given the complexity of the JWT setup, patching get_current_user
    # is easier for unit-testing the API.

    return client, user_id


def test_get_friend_code(client, app, test_user):
    """Test getting the friend code."""
    with app.app_context():
        # Ensure user is registered (has email)
        u = db.session.get(User, test_user.id)
        assert u is not None
        u.email = "registered@example.com"
        db.session.commit()
        user_id = u.id

    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        user = db.session.get(User, user_id)
        assert user is not None
        mock_get_user.return_value = user

        response = client.get("/api/friends/code")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "friend_code" in data
        assert len(data["friend_code"]) > 0


def test_reset_friend_code(client, app, test_user):
    """Test resetting the friend code."""
    with app.app_context():
        u = db.session.get(User, test_user.id)
        assert u is not None
        u.email = "registered@example.com"
        u.ensure_friend_code()
        old_code = u.friend_code
        db.session.commit()
        user_id = u.id

    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        user = db.session.get(User, user_id)
        assert user is not None
        mock_get_user.return_value = user

        response = client.post("/api/friends/code/reset")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["friend_code"] != old_code


def test_friend_request_flow(client, app):
    """Test sending and accepting a friend request."""
    with app.app_context():
        user1 = User(display_name="User 1", email="u1@example.com")
        user2 = User(display_name="User 2", email="u2@example.com")
        db.session.add_all([user1, user2])
        db.session.commit()

        user1.ensure_friend_code()
        user2.ensure_friend_code()
        code2 = user2.friend_code
        u1_id = user1.id
        u2_id = user2.id
        db.session.commit()

    # 1. User 1 sends request to User 2
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u1 = db.session.get(User, u1_id)
        mock_get_user.return_value = u1

        response = client.post("/api/friends/request", json={"friend_code": code2})
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    # 2. User 2 checks requests
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u2 = db.session.get(User, u2_id)
        mock_get_user.return_value = u2

        response = client.get("/api/friends/requests")
        assert response.status_code == 200
        data = response.get_json()
        assert len(data["requests"]) == 1
        assert data["requests"][0]["display_name"] == "User 1"
        assert data["requests"][0]["type"] == "received"
        request_id = data["requests"][0]["id"]

    # 3. User 2 accepts request
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u2 = db.session.get(User, u2_id)
        mock_get_user.return_value = u2

        response = client.post(
            f"/api/friends/requests/{request_id}/respond", json={"action": "accept"}
        )
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    # 4. Verify friendship exists and request is deleted
    with app.app_context():
        from app.models.friend_request import FriendRequest

        friendship = Friendship.get_friendship(u1_id, u2_id)
        assert friendship is not None
        request = FriendRequest.query.filter_by(
            requester_id=u1_id, recipient_id=u2_id
        ).first()
        assert request is None

    # 5. User 1 removes friend
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u1 = db.session.get(User, u1_id)
        mock_get_user.return_value = u1
        response = client.delete(f"/api/friends/{u2_id}")
        assert response.status_code == 200

    # 6. User 1 sends request again (should work now)
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u1 = db.session.get(User, u1_id)
        mock_get_user.return_value = u1
        response = client.post("/api/friends/request", json={"friend_code": code2})
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    # 7. User 2 rejects request
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u2 = db.session.get(User, u2_id)
        mock_get_user.return_value = u2
        response = client.get("/api/friends/requests")
        request_id = response.get_json()["requests"][0]["id"]
        response = client.post(
            f"/api/friends/requests/{request_id}/respond", json={"action": "reject"}
        )
        assert response.status_code == 200

    # 8. Verify request is deleted and User 1 can send again
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u1 = db.session.get(User, u1_id)
        mock_get_user.return_value = u1
        response = client.post("/api/friends/request", json={"friend_code": code2})
        assert response.status_code == 200
        assert response.get_json()["success"] is True


def test_remove_friend(client, app):
    """Test removing a friend."""
    with app.app_context():
        user1 = User(display_name="User 1", email="u1@example.com")
        user2 = User(display_name="User 2", email="u2@example.com")
        db.session.add_all([user1, user2])
        db.session.commit()

        friendship = Friendship.create_friendship(user1.id, user2.id)
        db.session.add(friendship)
        db.session.commit()
        u1_id = user1.id
        u2_id = user2.id

    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u1 = db.session.get(User, u1_id)
        mock_get_user.return_value = u1

        response = client.delete(f"/api/friends/{u2_id}")
        assert response.status_code == 200
        assert response.get_json()["success"] is True

    with app.app_context():
        assert Friendship.get_friendship(u1_id, u2_id) is None


def test_get_friends_list(client, app):
    """Test getting the friends list."""
    with app.app_context():
        user1 = User(display_name="User 1", email="u1@example.com")
        user2 = User(display_name="User 2", email="u2@example.com")
        db.session.add_all([user1, user2])
        db.session.commit()

        friendship = Friendship.create_friendship(user1.id, user2.id)
        db.session.add(friendship)
        db.session.commit()
        u1_id = user1.id

    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        u1 = db.session.get(User, u1_id)
        mock_get_user.return_value = u1

        response = client.get("/api/friends/list")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert len(data["friends"]) == 1
        assert data["friends"][0]["name"] == "User 2"
