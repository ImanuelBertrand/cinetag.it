"""Atomic-claim behavior for the email and notification queue drains.

These tests open a second DB connection inside the test, lock one row from
that connection, then run the cron drain from the test's normal session. The
drain uses SELECT FOR UPDATE SKIP LOCKED, so the locked row should be left
untouched. Two workers running the drain simultaneously would behave the
same way: each picks a disjoint set of rows.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.notification import Notification
from app.models.notification_channel import NotificationChannel
from app.models.user import User
from app.models.user_email import UserEmailQueue
from app.utils.email import queue_email, send_queued_emails
from app.utils.notifications import cron_send_notifications


@pytest.fixture
def _email_app_context(app):
    """Configure the app for url_for(_external=True) inside background tasks."""
    with app.test_request_context():
        app.config["SERVER_NAME"] = "localhost:8000"
        app.config["PREFERRED_URL_SCHEME"] = "http"
        yield


@pytest.mark.usefixtures("_email_app_context")
def test_send_queued_emails_skips_rows_locked_by_another_transaction(test_user):
    user = db.session.get(User, test_user.id)
    assert user is not None
    user.new_email = "new@example.com"
    db.session.commit()

    queue_email(user, "confirm")
    queue_email(user, "reset")

    ids = sorted(row.id for row in UserEmailQueue.query.all())
    assert len(ids) == 2
    locked_id, free_id = ids

    # Release the session before opening the separate transaction so we
    # cannot deadlock against ourselves on the locked row.
    db.session.commit()

    with db.engine.connect() as conn2:
        trans = conn2.begin()
        try:
            result = conn2.execute(
                text("SELECT id FROM user_email_queue WHERE id = :id FOR UPDATE"),
                {"id": locked_id},
            ).all()
            assert len(result) == 1

            with (
                patch("app.utils.email.send_confirmation_email") as send_confirm,
                patch("app.utils.email.send_password_reset_email") as send_reset,
            ):
                send_queued_emails()

            # The drain claimed and removed the free row, and sent for it.
            # The locked row is untouched.
            remaining = [row.id for row in UserEmailQueue.query.all()]
            assert remaining == [locked_id]
            # Exactly one of the two send funcs was called (the free row's type).
            assert send_confirm.call_count + send_reset.call_count == 1
        finally:
            trans.rollback()

    # After the lock is released a second drain picks up the remaining row.
    with (
        patch("app.utils.email.send_confirmation_email"),
        patch("app.utils.email.send_password_reset_email"),
    ):
        send_queued_emails()
    assert UserEmailQueue.query.count() == 0
    _ = free_id  # silence "unused" — clarifies intent that two rows existed


@pytest.mark.usefixtures("_email_app_context")
def test_send_queued_emails_dedupes_multiple_rows_per_user_and_type(test_user):
    """Two rows for the same (user, mail_type) result in one send."""
    user = db.session.get(User, test_user.id)
    assert user is not None
    user.new_email = "new@example.com"
    db.session.commit()

    queue_email(user, "confirm")
    queue_email(user, "confirm")
    assert UserEmailQueue.query.count() == 2

    with (
        patch("app.utils.email.send_confirmation_email") as send_confirm,
        patch("app.utils.email.send_password_reset_email"),
    ):
        send_queued_emails()

    assert UserEmailQueue.query.count() == 0
    assert send_confirm.call_count == 1


def _make_notification_fixtures(*, movie_id: int):
    user = User(
        display_name=f"Notif User {movie_id}",
        email=f"notif-{movie_id}@example.com",
        region="US",
        language="en",
    )
    db.session.add(user)
    db.session.flush()
    today = datetime.now(UTC).date()
    movie = Movie(
        id=movie_id,
        original_title=f"Movie {movie_id}",
        popularity=1.0,
        original_language="en",
    )
    db.session.add(movie)
    db.session.add(
        MovieRegionInfo(
            movie_id=movie_id, region="US", release_date=today + timedelta(days=5)
        )
    )
    db.session.add(
        MovieLanguageInfo(
            movie_id=movie_id,
            language="en",
            title=f"Movie {movie_id}",
            overview="overview",
        )
    )
    channel = NotificationChannel(user_id=user.id, mode="push", enabled=True)
    channel.days_in_advance = [3]
    channel.include_maybe_movies = False
    channel.notification_data = {
        "endpoint": "https://push.example.com/test",
        "keys": {"p256dh": "k", "auth": "a"},
    }
    db.session.add(channel)
    db.session.flush()
    notification = Notification(
        user_id=user.id,
        channel_id=channel.id,
        movie_id=movie_id,
        days_in_advance=3,
        scheduled_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    db.session.add(notification)
    db.session.commit()
    return notification


def test_cron_send_notifications_skips_rows_locked_by_another_transaction(app):
    with app.app_context():
        locked = _make_notification_fixtures(movie_id=9001)
        free = _make_notification_fixtures(movie_id=9002)
        locked_id = locked.id
        free_id = free.id

        # Release session before grabbing the second connection's lock.
        db.session.commit()

        with db.engine.connect() as conn2:
            trans = conn2.begin()
            try:
                conn2.execute(
                    text("SELECT id FROM notifications WHERE id = :id FOR UPDATE"),
                    {"id": locked_id},
                ).all()

                with patch(
                    "app.utils.notifications.send_notification", return_value=True
                ) as send:
                    cron_send_notifications()

                # send_notification was invoked only for the free row.
                assert send.call_count == 1
                sent_arg = send.call_args.args[0]
                assert sent_arg.id == free_id
            finally:
                trans.rollback()

        # The free row was marked sent; the locked row is still pending.
        free_row = db.session.get(Notification, free_id)
        locked_row = db.session.get(Notification, locked_id)
        assert free_row is not None
        assert locked_row is not None
        assert free_row.is_sent is True
        assert locked_row.is_sent is False
