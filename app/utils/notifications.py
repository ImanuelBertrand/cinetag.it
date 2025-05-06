import logging
from datetime import datetime, timedelta, date
from typing import Dict

from app.exceptions import WebPushSubscriptionExpiredError
from app.extensions import db
from app.models.movie_region_info import MovieRegionInfo
from app.models.notification import Notification
from app.models.notification_channel import NotificationChannel
from app.models.user_movie import UserMovie
from app.utils.email import send_email

_logger = logging.getLogger(__name__)


def cron_setup_notifications():
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
                f"Deleted {deleted_notifications} notifications "
                f"for disabled channel {channel.id}"
            )
            db.session.add(channel)
            db.session.commit()


def cron_send_notifications():
    scheduled_notifications = (
        Notification.query.join(NotificationChannel)
        .filter(
            Notification.is_sent.is_(False),
            Notification.scheduled_at <= datetime.utcnow(),
            NotificationChannel.enabled == True,
        )
        .order_by(Notification.scheduled_at.asc())
        .all()
    )
    _logger.info(f"Sending {len(scheduled_notifications)} notifications")

    for notification in scheduled_notifications:
        try:
            if not notification.channel.enabled:
                # In case the channel was disabled by a
                # failed notification earlier in the loop
                continue

            if send_notification(notification):
                notification.is_sent = True
                notification.sent_at = datetime.utcnow()
                db.session.add(notification)
                db.session.commit()
        except Exception as e:
            _logger.exception(
                f"Failed to send notification {notification.id}: {e}"
            )


def send_notification(notification: Notification):
    mode_methods = {
        "email": send_email_notification,
        "push": send_push_notification,
    }

    mode = notification.channel.mode

    if mode not in mode_methods:
        _logger.error(f"Unknown notification type: {notification.mode}")
        return False

    try:
        return mode_methods[mode](notification)
    except Exception as e:
        _logger.exception(f"Error sending notification {notification.id}: {e}")
        return False


def get_push_notification_content(
    notification: Notification,
) -> Dict[str, str] | None:
    # Get the movie data
    movie_data = notification.movie.get_localized_data(
        notification.user.language or "en"
    )
    movie_region_info = MovieRegionInfo.query.filter_by(
        movie_id=notification.movie_id, region=notification.user.region or "US"
    ).first()

    if not movie_region_info:
        _logger.error(f"No region info found for movie {notification.movie_id}")
        return None

    movie_title = movie_data["title"]
    release_date = movie_region_info.release_date
    days_till_release = (release_date - date.today()).days

    return {
        "title": f"Upcoming movie: {movie_title}",
        "body": f"'In {days_till_release} days!",
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
    from app.utils.webpush import send_web_push

    _logger.info(f"Sending push notification for {notification.id}")

    # Get the channel and check if it has subscription data
    channel = notification.channel
    if not channel or not channel.notification_data:
        _logger.error(
            f"No subscription data found for notification {notification.id}"
        )
        return False

    notification_content = get_push_notification_content(notification)
    if notification_content is None:
        _logger.error(f"Failed to get notification data for {notification.id}")
        return False

    # Send the push notification
    try:
        subscription_info = channel.notification_data
        return send_web_push(subscription_info, notification_content)
    except WebPushSubscriptionExpiredError:
        _logger.warning(
            f"Push subscription expired for channel {channel.id}, "
            f"disabling channel"
        )
        # Disable the notification channel
        channel.enabled = False
        db.session.add(channel)
        db.session.commit()
        return False
    except Exception as e:
        _logger.exception(f"Error sending push notification: {e}")
        return False


def send_email_notification(notification: Notification):
    user_mail = notification.user.email
    movie_data = notification.movie.get_localized_data(notification.user.region)
    movie_region_info = MovieRegionInfo.query.filter_by(
        movie_id=notification.movie_id, region=notification.user.region
    ).first()
    movie_title = movie_data["title"]
    release_date = movie_region_info.release_date
    days_till_release = (release_date - date.today()).days
    body = (
        f"Hello! You have a movie '{movie_title}' "
        f"coming up in {days_till_release} days."
    )
    subject = f"Upcoming movie ({days_till_release} days): {movie_title}"
    _logger.info(f"Email notification for {notification.id} to {user_mail}")
    return send_email(user_mail, subject, body)


def setup_notifications(channel: NotificationChannel):
    valid_decisions = ["approve"]
    if channel.include_maybe_movies:
        valid_decisions.append("maybe")

    user_movies = UserMovie.query.filter(
        UserMovie.user_id == channel.user_id,
        UserMovie.decision.in_(valid_decisions),
    ).all()

    user_notifications = Notification.query.filter_by(channel_id=channel.id).all()
    user_notification_dict = {
        (n.movie_id, n.days_in_advance): n for n in user_notifications
    }

    user_region = channel.user.region

    scheduled_at_threshold = datetime.now() - timedelta(days=7)
    # Add missing notifications
    today = date.today()
    for user_movie in user_movies:
        region_info = MovieRegionInfo.query.filter_by(
            movie_id=user_movie.movie_id, region=user_region
        ).first()
        if region_info is None:
            continue
        if region_info.release_date <= today:
            continue
        for day in channel.days_in_advance:
            scheduled_date = region_info.release_date - timedelta(days=day)
            scheduled_date = datetime.combine(scheduled_date, datetime.min.time())
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

    # delete extra notifications, in case movies or days config has changed
    user_movie_ids = {m.movie_id for m in user_movies}
    for notification in user_notifications:
        if notification.is_sent:
            continue

        if (
            notification.movie_id not in user_movie_ids
            or notification.days_in_advance not in channel.days_in_advance
            or notification.scheduled_at < scheduled_at_threshold
        ):
            db.session.delete(notification)

    db.session.commit()
