import logging
from datetime import datetime

from flask import Blueprint, request, jsonify

from app.exceptions import UserFeedbackError
from app.extensions import db
from app.models.notification_channel import NotificationChannel
from app.models.user_movie import UserMovie
from app.services.user_service import (
    fetch_user_events,
    get_movies_based_on_filter,
    get_current_user,
)
from app.utils.notifications import setup_notifications
from app.utils.webpush import get_vapid_public_key_for_js

api = Blueprint("api", __name__)

_logger = logging.getLogger(__name__)


@api.route("/user/movies/review", methods=["POST"])
def review_movie():
    user = get_current_user()

    data = request.get_json()
    movie_id = data.get("movie_id")
    decision = data.get("decision")

    if decision not in ["approve", "disapprove", "maybe", "remove"]:
        return jsonify({"error": "Invalid decision value."}), 400

    user_movie = UserMovie.query.filter_by(
        user_id=user.id, movie_id=movie_id
    ).first()

    if decision == "remove":
        if user_movie:
            db.session.delete(user_movie)
            db.session.commit()
        result_decision = None
    else:
        if not user_movie:
            user_movie = UserMovie(
                user_id=user.id, movie_id=movie_id, decision=decision
            )
        else:
            user_movie.decision = decision
        db.session.add(user_movie)
        result_decision = user_movie.decision

    try:
        db.session.commit()
        return (
            jsonify(
                {
                    "success": True,
                    "decision_status": result_decision,
                }
            ),
            201,
        )
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 409


@api.route("/user/events", methods=["GET"])
def get_user_events():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404
    start = request.args.get("start")
    end = request.args.get("end")
    if not start or not end:
        return jsonify({"error": "Invalid date range."}), 400
    start = datetime.fromisoformat(start)
    end = datetime.fromisoformat(end)
    events = fetch_user_events(user, start, end)
    return jsonify(events)


@api.route("/movies/<filter_mode>", methods=["GET"])
def get_movies_api(filter_mode):
    user = get_current_user()

    try:
        # Get filter parameters
        need_imdb = True  # TODO toggle in user settings
        need_poster = True  # TODO toggle in user settings
        name_filter = request.args.get("name", "")

        # Get pagination parameters
        min_release_date = request.args.get("min_release_date")
        min_movie_id = request.args.get("min_movie_id")
        limit = int(request.args.get("limit", 50))

        # Convert min_release_date to datetime if provided
        if min_release_date:
            min_release_date = datetime.strptime(
                min_release_date, "%Y-%m-%d"
            ).date()

        # Convert min_movie_id to int if provided
        if min_movie_id:
            min_movie_id = int(min_movie_id)

        # Get movies with pagination
        result = get_movies_based_on_filter(
            user,
            filter_mode,
            need_imdb,
            need_poster,
            name_filter=name_filter,
            min_release_date=min_release_date,
            min_movie_id=min_movie_id,
            limit=limit,
        )

        return jsonify(
            {
                "success": True,
                "movies": result["movies"],
                "next_release_date": result["next_release_date"],
                "next_movie_id": result["next_movie_id"],
                "has_more": result["has_more"],
            }
        )
    except UserFeedbackError as e:
        return jsonify({"success": False, "error": str(e)})
    except Exception as e:
        _logger.exception(f"Error fetching movies: {e}")
        return jsonify({"success": False, "error": "Error fetching movies."})


@api.route("/calendar/reset-hashes", methods=["POST"])
def reset_calendar_hashes():
    """Reset the calendar hashes for the current user"""
    user = get_current_user()
    if not user:
        return jsonify(
            {
                "success": False,
                "error": "There was an error with your session. Please try again.",
            }
        )

    try:
        user.reset_calendar_hashes()
        db.session.commit()

        return jsonify(
            {
                "success": True,
                "message": "Calendar links have been reset successfully.",
            }
        )
    except Exception as e:
        _logger.exception(f"Error resetting calendar hashes: {e}")
        return jsonify(
            {
                "success": False,
                "error": "Error resetting calendar links.",
            }
        )


@api.errorhandler(400)
def bad_request(error):
    return jsonify({"error": "Bad Request"}), 400


@api.errorhandler(401)
def unauthorized(error):
    return jsonify({"error": "Unauthorized"}), 401


@api.errorhandler(403)
def forbidden(error):
    return jsonify({"error": "Forbidden"}), 403


@api.errorhandler(404)
def not_found(error):
    return jsonify({"error": "Not Found"}), 404


@api.route("/vapid-public-key", methods=["GET"])
def get_vapid_public_key():
    """Get the VAPID public key for push notifications"""
    try:
        return jsonify(
            {"success": True, "publicKey": get_vapid_public_key_for_js()}
        )
    except Exception as e:
        _logger.exception(f"Error getting VAPID public key: {e}")
        return (
            jsonify({"success": False, "error": "Error getting VAPID public key"}),
            500,
        )


@api.route("/check-push-subscription", methods=["POST"])
def check_push_subscription():
    """Check if a push subscription exists for the current user"""
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 401

    data = request.get_json()
    if not data or "endpoint" not in data:
        return jsonify({"success": False, "error": "Invalid request data"}), 400

    endpoint = data["endpoint"]

    # Check if the user has a push notification channel with this endpoint
    push_channels = NotificationChannel.query.filter_by(
        user_id=user.id, mode="push"
    ).all()

    for channel in push_channels:
        if (
            channel.notification_data
            and channel.notification_data.get("endpoint") == endpoint
        ):
            # Return the subscription settings along with the existence flag
            return jsonify(
                {
                    "success": True,
                    "exists": True,
                    "settings": {
                        "days_in_advance": channel.days_in_advance,
                        "include_maybe_movies": channel.include_maybe_movies,
                    },
                }
            )

    return jsonify({"success": True, "exists": False})


@api.route("/subscribe", methods=["POST"])
def subscribe_push():
    """Subscribe to push notifications"""
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 401

    data = request.get_json()
    if not data or "endpoint" not in data:
        return (
            jsonify({"success": False, "error": "Invalid subscription data"}),
            400,
        )

    # Extract notification settings if provided
    days_in_advance = data.get(
        "days_in_advance", [1, 3, 7]
    )  # Default values if not provided
    include_maybe_movies = data.get(
        "include_maybe_movies", True
    )  # Default value if not provided

    # Check if the user already has a push channel with this endpoint
    push_channels = NotificationChannel.query.filter_by(
        user_id=user.id, mode="push"
    ).all()

    existing_channel = None
    for channel in push_channels:
        if (
            channel.notification_data
            and channel.notification_data.get("endpoint") == data["endpoint"]
        ):
            existing_channel = channel
            break

    if existing_channel:
        # Update the existing channel
        existing_channel.notification_data = data
        existing_channel.enabled = True
        existing_channel.days_in_advance = days_in_advance
        existing_channel.include_maybe_movies = include_maybe_movies
        db.session.add(existing_channel)
    else:
        # Create a new push notification channel
        channel = NotificationChannel(user_id=user.id, mode="push", enabled=True)
        channel.notification_data = data
        channel.days_in_advance = days_in_advance
        channel.include_maybe_movies = include_maybe_movies
        db.session.add(channel)

    try:
        db.session.commit()

        # Set up notifications for this channel
        for channel in push_channels:
            if channel.enabled:
                setup_notifications(channel)

        return jsonify(
            {
                "success": True,
                "message": "Successfully subscribed to push notifications",
                "settings": {
                    "days_in_advance": days_in_advance,
                    "include_maybe_movies": include_maybe_movies,
                },
            }
        )
    except Exception as e:
        db.session.rollback()
        _logger.exception(f"Error subscribing to push notifications: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Error subscribing to push notifications",
                }
            ),
            500,
        )


@api.route("/update-push-settings", methods=["POST"])
def update_push_settings():
    """Update push notification settings"""
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 401

    data = request.get_json()
    if not data or "endpoint" not in data:
        return jsonify({"success": False, "error": "Invalid request data"}), 400

    endpoint = data["endpoint"]
    days_in_advance = data.get("days_in_advance")
    include_maybe_movies = data.get("include_maybe_movies")

    if days_in_advance is None and include_maybe_movies is None:
        return (
            jsonify({"success": False, "error": "No settings provided to update"}),
            400,
        )

    # Find the push notification channel with this endpoint
    push_channels = NotificationChannel.query.filter_by(
        user_id=user.id, mode="push"
    ).all()

    found = False
    for channel in push_channels:
        if (
            channel.notification_data
            and channel.notification_data.get("endpoint") == endpoint
        ):
            if days_in_advance is not None:
                channel.days_in_advance = days_in_advance
            if include_maybe_movies is not None:
                channel.include_maybe_movies = include_maybe_movies
            db.session.add(channel)
            found = True
            break

    if not found:
        return jsonify({"success": False, "error": "Subscription not found"}), 404

    try:
        db.session.commit()

        # Set up notifications for this channel
        for channel in push_channels:
            if channel.enabled:
                setup_notifications(channel)

        return jsonify(
            {
                "success": True,
                "message": "Successfully updated push notification settings",
                "settings": {
                    "days_in_advance": days_in_advance
                    if days_in_advance is not None
                    else "",
                    "include_maybe_movies": include_maybe_movies
                    if include_maybe_movies is not None
                    else True,
                },
            }
        )
    except Exception as e:
        db.session.rollback()
        _logger.exception(f"Error updating push notification settings: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Error updating push notification settings",
                }
            ),
            500,
        )


@api.route("/unsubscribe", methods=["POST"])
def unsubscribe_push():
    """Unsubscribe from push notifications"""
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 401

    data = request.get_json()
    if not data or "endpoint" not in data:
        return jsonify({"success": False, "error": "Invalid request data"}), 400

    endpoint = data["endpoint"]

    # Find and disable the push notification channel with this endpoint
    push_channels = NotificationChannel.query.filter_by(
        user_id=user.id, mode="push"
    ).all()

    found = False
    for channel in push_channels:
        if (
            channel.notification_data
            and channel.notification_data.get("endpoint") == endpoint
        ):
            channel.enabled = False
            db.session.add(channel)
            found = True

    if not found:
        return jsonify({"success": False, "error": "Subscription not found"}), 404

    try:
        db.session.commit()
        return jsonify(
            {
                "success": True,
                "message": "Successfully unsubscribed from push notifications",
            }
        )
    except Exception as e:
        db.session.rollback()
        _logger.exception(f"Error unsubscribing from push notifications: {e}")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Error unsubscribing from push notifications",
                }
            ),
            500,
        )


@api.errorhandler(500)
def internal_server_error(error):
    return jsonify({"error": "Internal Server Error"}), 500
