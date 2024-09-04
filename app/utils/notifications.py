import logging
import traceback
from datetime import datetime

from app.extensions import db
from app.models.notification import Notification
from app.models.notification_channel import NotificationChannel
from app.models.user_movie import UserMovie
from app.utils.email import send_email

_logger = logging.getLogger(__name__)


def cron_setup_notifications():
    # TODO performance in case of many users
    channels = NotificationChannel.query.all()
    for channel in channels:
        setup_notifications(channel)


def cron_send_notifications():
    unset_notifications = Notification.query.filter_by(sent=False).all()
    for notification in unset_notifications:
        try:
            if send_notification(notification):
                notification.sent = True
                notification.sent_at = datetime.utcnow()
        except Exception as e:
            _logger.error(
                f"Failed to send notification {notification.id}: "
                f"#{e}\n{traceback.format_exc()}"
            )


def send_notification(notification: Notification):
    type_methods = {
        "email": send_email_notification,
        "push": send_push_notification,
    }

    if notification.mode not in type_methods:
        _logger.error(f"Unknown notification type: {notification.mode}")
        return False

    return type_methods[notification.mode](notification)


def send_push_notification(notification: Notification):
    # TODO implement push notification
    _logger.info(f"Push notification for {notification.id}")
    pass


def send_email_notification(notification: Notification):
    user_mail = notification.user.email
    movie_title = notification.movie.title
    days_in_advance = notification.days_in_advance
    body = (
        f"Hello! You have a movie '{movie_title}' "
        f"coming up in {days_in_advance} days."
    )

    return send_email(user_mail, "Movie Reminder", body)


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

    # Add missing notifications
    for user_movie in user_movies:
        for day in channel.days_in_advance:
            if (user_movie.movie_id, day) not in user_notification_dict:
                notification = Notification(
                    user_id=channel.user_id,
                    channel_id=channel.id,
                    movie_id=user_movie.movie_id,
                    days_in_advance=day,
                )
                db.session.add(notification)

    # delete extra notifications, in case movies or days config has changed
    user_movie_ids = {m.movie_id for m in user_movies}
    for notification in user_notifications:
        if (
            notification.movie_id not in user_movie_ids
            or notification.days_in_advance not in channel.days_in_advance
        ):
            db.session.delete(notification)

    db.session.commit()
