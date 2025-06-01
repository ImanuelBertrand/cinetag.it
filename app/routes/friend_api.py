import logging

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.friend_request import FriendRequest
from app.models.friendship import Friendship
from app.models.user import User
from app.services.user_service import get_current_user

friend_api = Blueprint("friend_api", __name__)

_logger = logging.getLogger(__name__)


@friend_api.route("/code", methods=["GET"])
def get_friend_code():
    """Get the current user's friend code"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        # Ensure the user has a friend code
        friend_code = user.ensure_friend_code()
        db.session.commit()

        return jsonify({"success": True, "friend_code": friend_code})
    except Exception:
        db.session.rollback()
        _logger.exception("Error getting friend code")
        return (
            jsonify({"success": False, "error": "Error getting friend code."}),
            500,
        )


@friend_api.route("/code/reset", methods=["POST"])
def reset_friend_code():
    """Reset the current user's friend code"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        # Reset the user's friend code
        friend_code = user.reset_friend_code()
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "friend_code": friend_code,
                "message": "Friend code has been reset successfully.",
            }
        )
    except Exception:
        db.session.rollback()
        _logger.exception("Error resetting friend code")
        return (
            jsonify({"success": False, "error": "Error resetting friend code."}),
            500,
        )


@friend_api.route("/request", methods=["POST"])
def send_friend_request():
    """Send a friend request to another user by friend code"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json()
    friend_code = data.get("friend_code")

    if not friend_code:
        return (
            jsonify({"success": False, "error": "Friend code is required."}),
            400,
        )

    try:
        # Find the user with the given friend code
        friend = User.query.filter_by(friend_code=friend_code).first()
        if not friend:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "User with this friend code not found.",
                    }
                ),
                404,
            )

        # Check if the user is trying to add themselves
        if friend.id == user.id:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "You cannot add yourself as a friend.",
                    }
                ),
                400,
            )

        # Check if a friendship already exists
        existing_friendship = Friendship.get_friendship(user.id, friend.id)

        if existing_friendship:
            return (
                jsonify(
                    {
                        "success": False,
                        "error": "You are already friends with this user.",
                    }
                ),
                400,
            )

        # Check if a friend request already exists
        existing_request = FriendRequest.query.filter_by(
            requester_id=user.id, recipient_id=friend.id
        ).first()

        if existing_request:
            if existing_request.status == "pending":
                return (
                    jsonify(
                        {"success": False, "error": "Friend request already sent."}
                    ),
                    400,
                )
            if existing_request.status == "rejected":
                # Update the existing request to pending
                existing_request.status = "pending"
                db.session.add(existing_request)
                db.session.commit()
                return jsonify(
                    {
                        "success": True,
                        "message": "Friend request sent successfully.",
                    }
                )

        # Check if the other user has already sent a request
        reverse_request = FriendRequest.query.filter_by(
            requester_id=friend.id, recipient_id=user.id
        ).first()

        if reverse_request and reverse_request.status == "pending":
            # Accept the reverse request automatically
            reverse_request.status = "accepted"
            db.session.add(reverse_request)

            # Create a single friendship record representing
            # the bidirectional relationship
            friendship = Friendship.create_friendship(user.id, friend.id)
            db.session.add(friendship)
            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "message": "Friend request accepted. You are now friends.",
                }
            )

        # Create a new friend request
        friend_request = FriendRequest(
            requester_id=user.id, recipient_id=friend.id, status="pending"
        )
        db.session.add(friend_request)
        db.session.commit()
    except Exception:
        db.session.rollback()
        _logger.exception("Error sending friend request")
        return (
            jsonify({"success": False, "error": "Error sending friend request."}),
            500,
        )
    else:
        return jsonify(
            {"success": True, "message": "Friend request sent successfully."}
        )


@friend_api.route("/requests", methods=["GET"])
def get_friend_requests():
    """Get the current user's pending friend requests"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        # Get pending friend requests received by the user
        pending_requests = FriendRequest.query.filter_by(
            recipient_id=user.id, status="pending"
        ).all()

        requests = []
        for request in pending_requests:
            requester = db.session.get(User, request.requester_id)
            if requester:
                requests.append(
                    {
                        "id": request.id,
                        "requester_id": requester.id,
                        "requester_name": requester.display_name or "User",
                        "created_at": request.created_at.isoformat(),
                    }
                )

        return jsonify({"success": True, "requests": requests})
    except Exception:
        _logger.exception("Error getting friend requests")
        return (
            jsonify({"success": False, "error": "Error getting friend requests."}),
            500,
        )


@friend_api.route("/requests/<int:request_id>/respond", methods=["POST"])
def respond_to_friend_request(request_id):
    """Respond to a friend request"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json()
    action = data.get("action")

    if action not in ["accept", "reject"]:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Invalid action. Must be 'accept' or 'reject'.",
                }
            ),
            400,
        )

    try:
        # Find the friend request
        friend_request = FriendRequest.query.filter_by(
            id=request_id, recipient_id=user.id, status="pending"
        ).first()

        if not friend_request:
            return (
                jsonify({"success": False, "error": "Friend request not found."}),
                404,
            )

        if action == "accept":
            # Update the request status
            friend_request.status = "accepted"
            db.session.add(friend_request)

            # Create a single friendship record representing
            # the bidirectional relationship
            friendship = Friendship.create_friendship(
                user.id, friend_request.requester_id
            )
            db.session.add(friendship)
            db.session.commit()

            return jsonify(
                {
                    "success": True,
                    "message": "Friend request accepted. You are now friends.",
                }
            )
        # reject
        friend_request.status = "rejected"
        db.session.add(friend_request)
        db.session.commit()

    except Exception:
        db.session.rollback()
        _logger.exception("Error responding to friend request")
        return (
            jsonify({"success": False, "error": "Error responding to friend request."}),
            500,
        )
    else:
        return jsonify({"success": True, "message": "Friend request rejected."})


@friend_api.route("/list", methods=["GET"])
def get_friends_list():
    """Get the current user's friends list"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        # Get all friends with their details in a single efficient query
        friends = Friendship.get_friends_with_details(user.id)
        return jsonify({"success": True, "friends": friends})
    except Exception:
        _logger.exception("Error getting friends list")
        return (
            jsonify({"success": False, "error": "Error getting friends list."}),
            500,
        )


@friend_api.route("/<int:friend_id>", methods=["DELETE"])
def remove_friend(friend_id):
    """Remove a friend from the user's friends list"""
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    try:
        # Get the friendship record
        friendship = Friendship.get_friendship(user.id, friend_id)
        if friendship:
            db.session.delete(friendship)

        db.session.commit()
    except Exception:
        db.session.rollback()
        _logger.exception("Error removing friend")
        return jsonify({"success": False, "error": "Error removing friend."}), 500
    else:
        return jsonify({"success": True, "message": "Friend removed successfully."})
