from unittest.mock import patch

from app.extensions import db
from app.models.friend_request import FriendRequest
from app.models.user import User


def test_get_friend_requests_sent_and_received(client, app, test_user):
    """Test that get_friend_requests returns both sent and received requests."""

    with app.app_context():
        # Create another user to send a request to
        user2 = User(
            display_name="User 2", email="user2@example.com", region="US", language="en"
        )
        # Create another user to receive a request from
        user3 = User(
            display_name="User 3", email="user3@example.com", region="US", language="en"
        )
        db.session.add(user2)
        db.session.add(user3)
        db.session.commit()

        # Sent request from test_user to user2
        sent_request = FriendRequest(
            requester_id=test_user.id, recipient_id=user2.id, status="pending"
        )
        # Received request from user3 to test_user
        received_request = FriendRequest(
            requester_id=user3.id, recipient_id=test_user.id, status="pending"
        )

        db.session.add(sent_request)
        db.session.add(received_request)
        db.session.commit()

        test_user_id = test_user.id
        user2_id = user2.id
        user3_id = user3.id

    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        user = db.session.get(User, test_user_id)
        mock_get_user.return_value = user

        response = client.get("/api/friends/requests")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

        # This is where it's expected to fail before the fix
        # Currently it only returns received requests, so length would be 1
        requests = data["requests"]

        # We want both sent and received
        assert len(requests) == 2

        # Check for received request
        received = next((r for r in requests if r["type"] == "received"), None)
        assert received is not None
        assert received["display_name"] == "User 3"
        assert received["user_id"] == user3_id

        # Check for sent request
        sent = next((r for r in requests if r["type"] == "sent"), None)
        assert sent is not None
        assert sent["display_name"] == "User 2"
        assert sent["user_id"] == user2_id
        sent_request_id = sent["id"]

    # Test cancelling the sent request
    with (
        patch("app.routes.friend_api.get_current_user") as mock_get_user,
        app.app_context(),
    ):
        user = db.session.get(User, test_user_id)
        mock_get_user.return_value = user

        response = client.delete(f"/api/friends/requests/{sent_request_id}")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["message"] == "Friend request cancelled."

        # Verify it's gone from the database
        assert db.session.get(FriendRequest, sent_request_id) is None
