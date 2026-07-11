import logging

from app.extensions import db
from app.models.friend_request import FriendRequest
from app.models.friendship import Friendship
from app.models.user import User

_logger = logging.getLogger(__name__)

# Uniform "request sent" response. Returned for both a genuine send and an
# unknown friend code so an attacker can't tell valid codes from invalid ones
# (SEC-17). The rate limit on the endpoint makes probing the ~48-bit code space
# infeasible on top of this.
_FRIEND_REQUEST_SENT = (True, "Friend request sent successfully.", 200)


def send_friend_request_service(user: User, friend_code: str):
    """
    Business logic for sending a friend request.
    Returns a tuple (success, message, status_code)
    """
    # Find the user with the given friend code
    friend = User.query.filter_by(friend_code=friend_code).first()
    if not friend:
        # Same response as a real send — don't disclose that the code is invalid.
        return _FRIEND_REQUEST_SENT

    # Check if the user is trying to add themselves
    if friend.id == user.id:
        return False, "You cannot add yourself as a friend.", 400

    # Check if a friendship already exists
    existing_friendship = Friendship.get_friendship(user.id, friend.id)
    if existing_friendship:
        return False, "You are already friends with this user.", 400

    # Check if a friend request already exists (outgoing)
    existing_request = FriendRequest.query.filter_by(
        requester_id=user.id, recipient_id=friend.id
    ).first()

    if existing_request:
        if existing_request.status == "pending":
            return False, "Friend request already sent.", 400

        # If the request was rejected or accepted (though it should be deleted now),
        # we can just delete it and create a new one, or just update it to pending.
        # Accepted/rejected requests should be deleted, but for robustness,
        # we handle any non-pending existing request by resetting it.
        existing_request.status = "pending"
        db.session.add(existing_request)
        db.session.commit()
        return _FRIEND_REQUEST_SENT

    # Check if the other user has already sent a request (incoming)
    reverse_request = FriendRequest.query.filter_by(
        requester_id=friend.id, recipient_id=user.id
    ).first()

    if reverse_request and reverse_request.status == "pending":
        # Delete the reverse request as it's now fulfilled
        db.session.delete(reverse_request)

        # Create a single friendship record representing the bidirectional relationship
        friendship = Friendship.create_friendship(user.id, friend.id)
        db.session.add(friendship)
        db.session.commit()

        return True, "Friend request accepted. You are now friends.", 200

    # Create a new friend request
    friend_request = FriendRequest(
        requester_id=user.id, recipient_id=friend.id, status="pending"
    )
    db.session.add(friend_request)
    db.session.commit()

    return True, "Friend request sent successfully.", 200


def respond_to_friend_request_service(user: User, request_id: int, action: str):
    """
    Business logic for responding to a friend request.
    Returns a tuple (success, message, status_code)
    """
    # Find the friend request
    friend_request = FriendRequest.query.filter_by(
        id=request_id, recipient_id=user.id, status="pending"
    ).first()

    if not friend_request:
        return False, "Friend request not found.", 404

    if action == "accept":
        # Delete the request as it's now fulfilled
        db.session.delete(friend_request)

        # Create a single friendship record representing the bidirectional relationship
        friendship = Friendship.create_friendship(user.id, friend_request.requester_id)
        db.session.add(friendship)
        db.session.commit()

        return True, "Friend request accepted. You are now friends.", 200

    # If action is "reject"
    db.session.delete(friend_request)
    db.session.commit()

    return True, "Friend request rejected.", 200
