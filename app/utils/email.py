import logging
import os
from datetime import UTC, datetime, timedelta
from typing import cast

from flask import current_app, url_for
from flask_mail import Message

from app.extensions import db, mail
from app.models.send_confirmation_mails import SentConfirmationMails
from app.models.user_email import UserEmailQueue
from app.utils.jwt_keys import encode_with_kid

_logger = logging.getLogger(__name__)


def send_email(to: str | list[str], subject: str, body: str) -> bool:
    sender = current_app.config["MAIL_DEFAULT_SENDER"]
    sender_name = current_app.config.get("MAIL_DEFAULT_SENDER_NAME")
    if sender_name:
        sender = (sender_name, sender)
    try:
        if isinstance(to, str):
            recipients: list[str | tuple[str, str]] = [to]
        else:
            recipients = cast("list[str | tuple[str, str]]", to)
        msg = Message(subject, recipients=recipients, body=body, sender=sender)
        mail.send(msg)
    except Exception:
        _logger.exception("Error sending email")
        return False
    else:
        return True


def generate_confirmation_token(user):
    return encode_with_kid(
        {
            "confirmation": user.id,
            "new_mail": user.new_email,
            "exp": datetime.now(UTC) + timedelta(hours=24),
        },
        "SECRET_KEY",
        "SECRET_KEY_ID",
    )


def send_confirmation_email(user) -> None:
    if not user.new_email:
        _logger.error(
            "Can't send confirmation email for user %s: no new email", user.id
        )
        return
    token = generate_confirmation_token(user)
    confirm_url = url_for("html.confirm_email", token=token, _external=True)
    subject = "Please confirm your email"
    body = (
        f"Hi,\n\nPlease click the link below to "
        f"confirm your email address:\n\n{confirm_url}\n\nThank you!"
    )
    mail_sent_log = SentConfirmationMails(email=user.new_email)
    db.session.add(mail_sent_log)
    send_email(user.new_email, subject, body)
    db.session.commit()


def generate_password_reset_token(user):
    user.password_reset_token = os.urandom(16).hex()[:32]
    db.session.add(user)
    db.session.commit()
    return encode_with_kid(
        {
            "reset_password": user.id,
            "exp": datetime.now(UTC) + timedelta(hours=1),
            "token": user.password_reset_token,
        },
        "SECRET_KEY",
        "SECRET_KEY_ID",
    )


def send_password_reset_email(user) -> None:
    token = generate_password_reset_token(user)
    reset_url = url_for("html.reset_password", token=token, _external=True)
    subject = "Password Reset Requested"
    body = (
        f"Hi,\n\nPlease click the link below "
        f"to reset your password:\n\n{reset_url}\n\nThank you!"
    )
    send_email(user.email, subject, body)


def queue_email(user, mail_type) -> None:
    if mail_type not in ["confirm", "reset"]:
        raise ValueError(f"Unknown mail type: {mail_type}")

    mail_queue_item = UserEmailQueue(user=user, mail_type=mail_type)
    db.session.add(mail_queue_item)
    db.session.commit()


# cron job to send mail
def send_queued_emails() -> None:
    """Drain the email queue atomically.

    Claims pending rows with SELECT FOR UPDATE SKIP LOCKED, deletes them, and
    commits before sending — so a concurrent caller (another worker, or a
    future manual trigger) either picks a disjoint set or gets nothing.

    Trade-off: if the process crashes after commit but before the SMTP send
    completes, that email is lost. The user can re-trigger the confirmation
    or password-reset flow to enqueue another. Avoiding a double-send is more
    important than guaranteeing delivery on the first attempt for these flows.
    """
    items = (
        UserEmailQueue.query.order_by(UserEmailQueue.id)
        .with_for_update(skip_locked=True)
        .all()
    )
    if not items:
        db.session.rollback()
        return

    # Capture the user references before committing the delete — after commit,
    # SQLAlchemy expires attributes by default, and the queue row itself is gone.
    unique_sends: dict[tuple[int, str], tuple] = {}
    for item in items:
        unique_sends.setdefault(
            (item.user_id, item.mail_type), (item.user, item.mail_type)
        )

    for item in items:
        db.session.delete(item)
    db.session.commit()

    for user, mail_type in unique_sends.values():
        try:
            if mail_type == "confirm":
                send_confirmation_email(user)
            elif mail_type == "reset":
                send_password_reset_email(user)
            else:
                _logger.error("Unknown mail type: %s", mail_type)
        except Exception:
            _logger.exception("Error sending %s mail to user %s", mail_type, user.id)
