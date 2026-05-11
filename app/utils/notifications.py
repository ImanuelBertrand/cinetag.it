import json
import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.errors import WebPushSubscriptionExpiredError
from app.extensions import db
from app.models.movie_region_info import MovieRegionInfo
from app.models.notification import Notification
from app.models.notification_channel import NotificationChannel
from app.models.user_movie import UserMovie
from app.utils.email import send_email
from app.utils.webpush import send_web_push

if TYPE_CHECKING:
    from collections.abc import Iterable

_logger = logging.getLogger(__name__)


def cron_setup_notifications() -> None:
    # TODO performance in case of many users
    channels = NotificationChannel.query.all()
    for channel in channels:
        if channel.enabled:
            setup_notifications(channel)
        else:
            deleted_notifications = Notification.query.filter_by(
                channel_id=channel.id,
                is_sent=False,  # if the channel is re-enabled, so we don't resend
            ).delete()
            _logger.info(
                "Deleted %s notifications for disabled channel %s",
                deleted_notifications,
                channel.id,
            )
            db.session.add(channel)
            db.session.commit()


def cron_send_notifications() -> None:
    """Send pending notifications atomically.

    Loads candidate IDs without locking, then processes each one in its own
    short transaction: SELECT FOR UPDATE SKIP LOCKED, re-check is_sent, send,
    mark sent, commit. A concurrent caller either picks disjoint rows
    (SKIP LOCKED) or sees is_sent=True after our commit and filters it out.

    Failed sends leave is_sent=False so the next cron tick re-attempts —
    preserving the existing retry-on-failure semantic.
    """
    pending_ids = [
        nid
        for (nid,) in db.session.query(Notification.id)
        .join(NotificationChannel)
        .filter(
            Notification.is_sent.is_(False),
            Notification.scheduled_at <= datetime.now(UTC),
            NotificationChannel.enabled.is_(True),
        )
        .order_by(Notification.scheduled_at.asc())
        .all()
    ]
    db.session.rollback()
    _logger.info("Sending %s notifications", len(pending_ids))

    sent_notifications: dict[int, set[int]] = defaultdict(set)
    for notification_id in pending_ids:
        try:
            _claim_and_send_notification(notification_id, sent_notifications)
        except Exception:
            db.session.rollback()
            _logger.exception("Failed to send notification %s", notification_id)


def _claim_and_send_notification(
    notification_id: int, sent_notifications: dict[int, set[int]]
) -> None:
    """Claim one notification with SKIP LOCKED, send it, and commit."""
    notification = (
        Notification.query.filter(
            Notification.id == notification_id,
            Notification.is_sent.is_(False),
        )
        .with_for_update(skip_locked=True)
        .first()
    )
    if notification is None:
        # Already sent by a concurrent caller, or currently locked by one.
        db.session.rollback()
        return

    if not notification.channel.enabled:
        # Channel may have been disabled (possibly by an earlier failed
        # send in this loop hitting WebPushSubscriptionExpiredError).
        db.session.rollback()
        return

    if notification.movie_id in sent_notifications[notification.user_id]:
        # Multiple reminders for the same user+movie collapse to one send.
        is_sent = True
    else:
        is_sent = send_notification(notification)

    if is_sent:
        notification.is_sent = True
        notification.sent_at = datetime.now(UTC)
        db.session.add(notification)
        sent_notifications[notification.user_id].add(notification.movie_id)
    db.session.commit()


def send_notification(notification: Notification):
    mode_methods = {
        "email": send_email_notification,
        "push": send_push_notification,
    }

    mode = notification.channel.mode

    if mode not in mode_methods:
        _logger.error("Unknown notification type: %s", notification.mode)
        return False

    try:
        return mode_methods[mode](notification)
    except Exception:
        _logger.exception("Error sending notification %s", notification.id)
        return False


def get_push_notification_content(
    notification: Notification,
) -> dict[str, str] | None:
    # Get the movie data
    movie_data = notification.movie.get_localized_data(
        notification.user.language or "en"
    )
    movie_region_info = MovieRegionInfo.query.filter_by(
        movie_id=notification.movie_id, region=notification.user.region or "US"
    ).first()

    if not movie_region_info:
        _logger.error("No region info found for movie %s", notification.movie_id)
        return None

    movie_title = movie_data["title"]
    release_date = movie_region_info.release_date
    days_till_release = (release_date - datetime.now(UTC).date()).days

    if abs(days_till_release - notification.days_in_advance) > max(
        notification.days_in_advance, 3
    ):
        _logger.warning(
            "Skipping push notification %s: days_till_release=%s "
            "but days_in_advance=%s",
            notification.id,
            days_till_release,
            notification.days_in_advance,
        )
        return None

    return {
        "title": f"Upcoming movie: {movie_title}",
        "body": f"In {days_till_release} days!",
        "icon": f"/poster/500/{movie_data.get('poster_path', 'default.jpg')}",
        "url": f"/movie/{notification.movie_id}",
    }


def send_push_notification(notification: Notification):
    """
    Send a push notification to the user's browser.

    Args:
        notification: The Notification object to send

    Returns:
        True if successful, False otherwise
    """

    _logger.info("Sending push notification for %s", notification.id)

    # Get the channel and check if it has subscription data
    channel = notification.channel
    if not channel or not channel.notification_data:
        _logger.error("No subscription data found for notification %s", notification.id)
        return False

    notification_content = get_push_notification_content(notification)
    if notification_content is None:
        _logger.error("Failed to get notification data for %s", notification.id)
        return False

    # Send the push notification
    try:
        subscription_info = channel.notification_data
        return send_web_push(subscription_info, notification_content)
    except WebPushSubscriptionExpiredError:
        _logger.warning(
            "Push subscription expired for channel %s, disabling channel", channel.id
        )
        # Disable the notification channel
        channel.enabled = False
        db.session.add(channel)
        db.session.commit()
        return False
    except Exception:
        _logger.exception("Error sending push notification")
        return False


def send_email_notification(notification: Notification):
    user_mail = notification.user.email
    if not user_mail:
        _logger.error("No email address for user %s", notification.user_id)
        return False
    user_region = notification.user.region or "US"
    movie_data = notification.movie.get_localized_data(user_region)
    movie_region_info = MovieRegionInfo.query.filter_by(
        movie_id=notification.movie_id, region=user_region
    ).first()

    if not movie_region_info:
        _logger.error("No region info found for movie %s", notification.movie_id)
        return False

    movie_title = movie_data["title"]
    release_date = movie_region_info.release_date
    days_till_release = (release_date - datetime.now(UTC).date()).days

    if abs(days_till_release - notification.days_in_advance) > max(
        notification.days_in_advance, 3
    ):
        _logger.warning(
            "Skipping email notification %s: days_till_release=%s "
            "but days_in_advance=%s",
            notification.id,
            days_till_release,
            notification.days_in_advance,
        )
        return False

    body = (
        f"Hello! You have a movie '{movie_title}' "
        f"coming up in {days_till_release} days."
    )
    subject = f"Upcoming movie ({days_till_release} days): {movie_title}"
    _logger.info("Email notification for %s to %s", notification.id, user_mail)
    return send_email(user_mail, subject, body)


def add_missing_notifications(
    channel: NotificationChannel,
    user_movies: Iterable[UserMovie],
    user_notifications: Iterable[Notification],
) -> None:
    scheduled_at_threshold = datetime.now(UTC) - timedelta(days=7)
    today = datetime.now(UTC).date()
    user_region = channel.user.region
    user_notification_dict = {
        (n.movie_id, n.days_in_advance): n for n in user_notifications
    }
    for user_movie in user_movies:
        region_info = MovieRegionInfo.query.filter_by(
            movie_id=user_movie.movie_id, region=user_region
        ).first()
        if region_info is None:
            continue
        if region_info.release_date <= today:
            continue
        days_in_advance = channel.days_in_advance
        if isinstance(days_in_advance, str):
            try:
                days_in_advance = json.loads(days_in_advance)
            except json.JSONDecodeError, ValueError:
                days_in_advance = []
        for day in days_in_advance:
            try:
                days_val = int(day)
            except ValueError, TypeError:
                _logger.exception(
                    "Invalid day value in notification channel %s: %s", channel.id, day
                )
                continue

            scheduled_date = region_info.release_date - timedelta(days=days_val)
            scheduled_date = datetime.combine(
                scheduled_date, datetime.min.time(), tzinfo=UTC
            )
            if scheduled_date < scheduled_at_threshold:
                continue
            if (user_movie.movie_id, day) not in user_notification_dict:
                notification = Notification(
                    user_id=channel.user_id,
                    channel_id=channel.id,
                    movie_id=user_movie.movie_id,
                    days_in_advance=day,
                    scheduled_at=scheduled_date,
                )
                db.session.add(notification)


def delete_outdated_notifications(
    channel: NotificationChannel,
    user_movies: Iterable[UserMovie],
    user_notifications: Iterable[Notification],
) -> None:
    scheduled_at_threshold = datetime.now(UTC) - timedelta(days=7)
    user_movie_ids = {m.movie_id for m in user_movies}
    user_region = channel.user.region

    # Batch-load region infos to avoid N+1 queries
    notification_movie_ids = {n.movie_id for n in user_notifications if not n.is_sent}
    region_infos = (
        {
            ri.movie_id: ri
            for ri in MovieRegionInfo.query.filter(
                MovieRegionInfo.movie_id.in_(notification_movie_ids),
                MovieRegionInfo.region == user_region,
            ).all()
        }
        if notification_movie_ids and user_region
        else {}
    )

    for notification in user_notifications:
        if notification.is_sent:
            continue

        if (
            notification.movie_id not in user_movie_ids
            or notification.days_in_advance not in channel.days_in_advance
            or notification.scheduled_at is None
            or notification.scheduled_at < scheduled_at_threshold
        ):
            db.session.delete(notification)
            continue

        # Delete notifications whose schedule no longer matches the current
        # release date (e.g. release date was pushed back or pulled forward)
        region_info = region_infos.get(notification.movie_id)
        if region_info is None:
            db.session.delete(notification)
            continue

        expected_scheduled = datetime.combine(
            region_info.release_date - timedelta(days=notification.days_in_advance),
            datetime.min.time(),
            tzinfo=UTC,
        )
        if notification.scheduled_at != expected_scheduled:
            db.session.delete(notification)


def setup_notifications(channel: NotificationChannel) -> None:
    valid_decisions = ["approve"]
    if channel.include_maybe_movies:
        valid_decisions.append("maybe")

    user_movies = UserMovie.query.filter(
        UserMovie.user_id == channel.user_id,
        UserMovie.decision.in_(valid_decisions),
    ).all()

    user_notifications = Notification.query.filter_by(channel_id=channel.id).all()

    add_missing_notifications(channel, user_movies, user_notifications)
    delete_outdated_notifications(channel, user_movies, user_notifications)

    db.session.commit()
