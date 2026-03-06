import logging

from flask import Blueprint, jsonify, request

from app.extensions import db
from app.models.friend_request import FriendRequest
from app.models.friendship import Friendship
from app.models.user import User
from app.services.friend_service import (
    respond_to_friend_request_service,
    send_friend_request_service,
)
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
        success, message, status_code = send_friend_request_service(user, friend_code)

        if not success:
            return jsonify({"success": False, "error": message}), status_code

        return jsonify({"success": True, "message": message}), status_code
    except Exception:
        db.session.rollback()
        _logger.exception("Error sending friend request")
        return (
            jsonify({"success": False, "error": "Error sending friend request."}),
            500,
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
        success, message, status_code = respond_to_friend_request_service(
            user, request_id, action
        )

        if not success:
            return jsonify({"success": False, "error": message}), status_code

        return jsonify({"success": True, "message": message}), status_code

    except Exception:
        db.session.rollback()
        _logger.exception("Error responding to friend request")
        return (
            jsonify({"success": False, "error": "Error responding to friend request."}),
            500,
        )


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
