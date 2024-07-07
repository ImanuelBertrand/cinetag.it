import logging
import os
from collections import defaultdict
from datetime import datetime, timedelta

import jwt
from flask import current_app, url_for
from flask_mail import Message

from app.extensions import mail, db
from app.models import UserEmailQueue, SentConfirmationMails

_logger = logging.getLogger(__name__)


def send_email(to, subject, body):
    msg = Message(
        subject,
        recipients=[to],
        body=body,
        sender=current_app.config["MAIL_DEFAULT_SENDER"],
    )
    mail.send(msg)


def generate_confirmation_token(user):
    token = jwt.encode(
        {
            "confirmation": user.id,
            "new_mail": user.new_email,
            "exp": datetime.utcnow() + timedelta(hours=24),
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return token


def send_confirmation_email(user):
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
    return jwt.encode(
        {
            "reset_password": user.id,
            "exp": datetime.utcnow() + timedelta(hours=1),
            "token": user.password_reset_token,
        },
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def send_password_reset_email(user):
    token = generate_password_reset_token(user)
    reset_url = url_for("html.reset_password", token=token, _external=True)
    subject = "Password Reset Requested"
    body = (
        f"Hi,\n\nPlease click the link below "
        f"to reset your password:\n\n{reset_url}\n\nThank you!"
    )
    send_email(user.email, subject, body)


def queue_email(user, mail_type):
    if mail_type not in ["confirm", "reset"]:
        raise ValueError(f"Unknown mail type: {mail_type}")

    mail_queue_item = UserEmailQueue(user=user, mail_type=mail_type)
    db.session.add(mail_queue_item)
    db.session.commit()


# cron job to send mail
def send_queued_emails():
    send_dict = defaultdict(list)
    for item in UserEmailQueue.query.all():
        send_dict[(item.user, item.mail_type)].append(item)

    for (user, mail_type), items in send_dict.items():
        try:
            if mail_type == "confirm":
                send_confirmation_email(user)
            elif mail_type == "reset":
                send_password_reset_email(user)
            else:
                _logger.error(f"Unknown mail type: {mail_type}")

            for item in items:
                db.session.delete(item)
            db.session.commit()
        except Exception as e:
            _logger.exception(f"Error sending mail: {e}")
            db.session.rollback()
            _logger.error(f"Error sending mail: {e}")
