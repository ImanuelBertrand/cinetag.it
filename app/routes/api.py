import json
import logging
from datetime import UTC, date, datetime

from flask import Blueprint, jsonify, request

from app.errors import UserFeedbackError
from app.extensions import db
from app.models.notification_channel import NotificationChannel
from app.models.user_movie import UserMovie
from app.services.user_service import (
    fetch_user_events,
    get_current_user,
    get_movies_based_on_filter,
)
from app.utils.notifications import setup_notifications
from app.utils.webpush import get_vapid_public_key_for_js

api = Blueprint("api", __name__)

_logger = logging.getLogger(__name__)


@api.route("/user/movies/review", methods=["POST"])
def review_movie():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404

    data = request.get_json()
    movie_id = data.get("movie_id")
    decision = data.get("decision")

    if decision not in ["approve", "disapprove", "maybe", "remove"]:
        return jsonify({"error": "Invalid decision value."}), 400

    user_movie = UserMovie.query.filter_by(user_id=user.id, movie_id=movie_id).first()

    if decision == "remove":
        if user_movie:
            db.session.delete(user_movie)
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


@api.route("/user/events", methods=["GET"])
def get_user_events():
    user = get_current_user()
    if not user:
        return jsonify({"error": "User not found."}), 404
    start_str = request.args.get("start")
    end_str = request.args.get("end")
    if not start_str or not end_str:
        return jsonify({"error": "Invalid date range."}), 400
    start = datetime.fromisoformat(start_str)
    end = datetime.fromisoformat(end_str)
    events = fetch_user_events(user, start, end)
    return jsonify(events)


def _parse_cursor_args(
    args,
) -> tuple[date | None, int | None, float | None]:
    """Parse the keyset-pagination cursor query params."""
    min_release_date = args.get("min_release_date")
    min_movie_id = args.get("min_movie_id")
    min_popularity = args.get("min_popularity")

    release_val: date | None = None
    if min_release_date:
        release_val = (
            datetime.strptime(min_release_date, "%Y-%m-%d").replace(tzinfo=UTC).date()
        )
    movie_id_val = int(min_movie_id) if min_movie_id else None
    popularity_val = float(min_popularity) if min_popularity not in (None, "") else None
    return release_val, movie_id_val, popularity_val


def _parse_genre_ids(raw: str | None) -> list[int] | None:
    """Parse a comma-separated list of TMDB genre ids, ignoring junk."""
    if not raw:
        return None
    ids = []
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.append(int(part))
            except ValueError:
                continue
    return ids or None


@api.route("/movies/<filter_mode>", methods=["GET"])
def get_movies_api(filter_mode):
    user = get_current_user()

    try:
        # Get filter parameters
        need_imdb = True  # TODO toggle in user settings
        need_poster = True  # TODO toggle in user settings
        name_filter = request.args.get("name", "")
        friend_id = request.args.get("friend_id")

        # Sort order (release date by default) and genre filter
        sort = request.args.get("sort", "release")
        if sort not in ("release", "popularity"):
            sort = "release"
        genre_ids = _parse_genre_ids(request.args.get("genres"))

        # Get pagination parameters
        limit = int(request.args.get("limit", 50))
        min_release_date_val, min_movie_id_val, min_popularity_val = _parse_cursor_args(
            request.args
        )

        # Convert friend_id to int if provided
        if friend_id:
            try:
                friend_id = int(friend_id)
            except ValueError:
                return jsonify({"success": False, "error": "Invalid friend ID."})

        # Get movies with pagination
        result = get_movies_based_on_filter(
            user,
            filter_mode,
            need_imdb,
            need_poster,
            name_filter=name_filter,
            min_release_date=min_release_date_val,
            min_movie_id=min_movie_id_val,
            limit=limit,
            friend_id=friend_id,
            sort=sort,
            min_popularity=min_popularity_val,
            genre_ids=genre_ids,
        )

        # Prepare response
        response = {
            "success": True,
            "movies": result["movies"],
            "next_release_date": result["next_release_date"],
            "next_movie_id": result["next_movie_id"],
            "next_popularity": result["next_popularity"],
            "has_more": result["has_more"],
        }

        # Add friend information if available
        if "friend" in result:
            response["friend"] = result["friend"]

        result = jsonify(response)
    except UserFeedbackError as e:
        return jsonify({"success": False, "error": str(e)})
    except Exception:
        _logger.exception("Error fetching movies")
        return jsonify({"success": False, "error": "Error fetching movies."})
    else:
        return result


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
    except Exception:
        _logger.exception("Error resetting calendar hashes")
        return jsonify(
            {
                "success": False,
                "error": "Error resetting calendar links.",
            }
        )


@api.errorhandler(400)
def bad_request(error):  # pylint: disable=unused-argument
    return jsonify({"error": "Bad Request"}), 400


@api.errorhandler(401)
def unauthorized(error):  # pylint: disable=unused-argument
    return jsonify({"error": "Unauthorized"}), 401


@api.errorhandler(403)
def forbidden(error):  # pylint: disable=unused-argument
    return jsonify({"error": "Forbidden"}), 403


@api.errorhandler(404)
def not_found(error):  # pylint: disable=unused-argument
    return jsonify({"error": "Not Found"}), 404


@api.route("/vapid-public-key", methods=["GET"])
def get_vapid_public_key():
    """Get the VAPID public key for push notifications"""
    try:
        return jsonify({"success": True, "publicKey": get_vapid_public_key_for_js()})
    except Exception:
        _logger.exception("Error getting VAPID public key")
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


# (token found in UA, label). Order matters: more specific tokens first.
_UA_BROWSERS = (
    ("Edg", "Edge"),
    ("Firefox", "Firefox"),
    ("CriOS", "Chrome"),
    ("Chrome", "Chrome"),
    ("Safari", "Safari"),
)
_UA_OSES = (
    ("Windows", "Windows"),
    ("Android", "Android"),
    ("iPhone", "iPhone"),
    ("iPad", "iPad"),
    ("Macintosh", "macOS"),
    ("Mac OS", "macOS"),
    ("Linux", "Linux"),
)


def _summarize_user_agent(ua: str) -> str:
    """Best-effort human label for a device from its User-Agent string."""
    browser = next((label for token, label in _UA_BROWSERS if token in ua), "Browser")
    os_name = next((label for token, label in _UA_OSES if token in ua), "")
    return f"{browser} on {os_name}" if os_name else browser


def _device_label_from_data(data: dict | None) -> str:
    """Derive a push-device label from its stored notification data."""
    ua = (data or {}).get("user_agent")
    return _summarize_user_agent(ua) if ua else "Unknown device"


@api.route("/notification-channels", methods=["GET"])
def list_notification_channels():
    """List every notification channel the current user owns.

    Pass ?endpoint=<current push endpoint> to have the matching push channel
    flagged as `is_current_device`.
    """
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 401

    current_endpoint = request.args.get("endpoint")
    channels = (
        NotificationChannel.query.filter_by(user_id=user.id)
        .order_by(NotificationChannel.mode, NotificationChannel.id)
        .all()
    )

    result = []
    for channel in channels:
        data = channel.notification_data or {}
        is_push = channel.mode == "push"
        is_current = bool(
            is_push and current_endpoint and data.get("endpoint") == current_endpoint
        )
        result.append(
            {
                "id": channel.id,
                "mode": channel.mode,
                "enabled": bool(channel.enabled),
                # Normalize legacy rows (JSON strings, string elements) so the
                # settings page always receives a list of ints.
                "days_in_advance": _normalize_days_list(channel.days_in_advance) or [],
                "include_maybe_movies": bool(channel.include_maybe_movies),
                "created_at": (
                    channel.created_at.isoformat() if channel.created_at else None
                ),
                "device_label": (_device_label_from_data(data) if is_push else "Email"),
                "is_current_device": is_current,
                # An expiry-disabled channel carries this marker so the UI can
                # explain why it stopped (see send_push_notification).
                "disabled_reason": data.get("disabled_reason") if is_push else None,
            }
        )

    return jsonify({"success": True, "channels": result})


def _apply_channel_update(channel: NotificationChannel, data: dict) -> str | None:
    """Apply the updatable fields to a channel. Returns an error message for
    invalid input, None on success."""
    if "enabled" in data:
        channel.enabled = bool(data["enabled"])
        # Re-enabling clears any expiry warning left by the push handler.
        if channel.enabled and (channel.notification_data or {}).get("disabled_reason"):
            new_data = dict(channel.notification_data or {})
            new_data.pop("disabled_reason", None)
            channel.notification_data = new_data

    if "days_in_advance" in data:
        days = _normalize_days_list(data["days_in_advance"])
        if days is None:
            return "days_in_advance must be a list of numbers"
        channel.days_in_advance = days

    if "include_maybe_movies" in data:
        channel.include_maybe_movies = bool(data["include_maybe_movies"])

    return None


@api.route("/notification-channels/<int:channel_id>", methods=["POST"])
def update_notification_channel(channel_id):
    """Update enabled / days_in_advance / include_maybe_movies for any channel
    the current user owns."""
    user = get_current_user()
    if not user:
        return jsonify({"success": False, "error": "User not found"}), 401

    channel = NotificationChannel.query.filter_by(
        id=channel_id, user_id=user.id
    ).first()
    if not channel:
        return jsonify({"success": False, "error": "Channel not found"}), 404

    error = _apply_channel_update(channel, request.get_json() or {})
    if error:
        return jsonify({"success": False, "error": error}), 400

    db.session.add(channel)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        _logger.exception("Error updating notification channel %s", channel_id)
        return (
            jsonify({"success": False, "error": "Error updating channel"}),
            500,
        )

    # The channel change is persisted at this point; a failure while
    # rescheduling must not be reported as a failed update — the hourly
    # notification cron reconciles the schedule anyway.
    if channel.enabled:
        try:
            setup_notifications(channel)
        except Exception:
            db.session.rollback()
            _logger.exception(
                "Error rescheduling notifications for channel %s", channel_id
            )

    return jsonify({"success": True})


DEFAULT_DAYS_IN_ADVANCE = [0, 1, 3, 7]


def _normalize_days_list(value) -> list[int] | None:
    """Coerce a days_in_advance value to a sorted list of unique non-negative
    ints. Handles legacy JSON-string rows and string elements from arbitrary
    clients — a str day like "2" would otherwise break the (movie_id, day)
    notification dedup key and re-send the same reminder every hour.
    Returns None when the value is not a list at all."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except json.JSONDecodeError, ValueError:
            return None
    if not isinstance(value, list):
        return None
    days = set()
    for item in value:
        try:
            day = int(item)
        except TypeError, ValueError:
            continue
        if day >= 0:
            days.add(day)
    return sorted(days)


def _parse_days_in_advance(data: dict) -> list[int]:
    days = _normalize_days_list(data.get("days_in_advance"))
    if days is None:
        return list(DEFAULT_DAYS_IN_ADVANCE)
    return days


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

    # Store a device hint so this channel can be labeled on the settings page.
    data["user_agent"] = request.headers.get("User-Agent")

    # Extract notification settings if provided
    days_in_advance = _parse_days_in_advance(data)
    include_maybe_movies = data.get("include_maybe_movies", True)

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
    except Exception:
        db.session.rollback()
        _logger.exception("Error subscribing to push notifications")
        return (
            jsonify(
                {
                    "success": False,
                    "error": "Error subscribing to push notifications",
                }
            ),
            500,
        )


def _find_and_update_subscription(
    push_channels: list[NotificationChannel],
    endpoint: str,
    days_in_advance: list[int] | None,
    include_maybe_movies: bool | None,
) -> bool:
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
            return True

    return False


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

    if not _find_and_update_subscription(
        push_channels, endpoint, days_in_advance, include_maybe_movies
    ):
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
    except Exception:
        db.session.rollback()
        _logger.exception("Error updating push notification settings")
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
    except Exception:
        db.session.rollback()
        _logger.exception("Error unsubscribing from push notifications")
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
def internal_server_error(error):  # pylint: disable=unused-argument
    return jsonify({"error": "Internal Server Error"}), 500
