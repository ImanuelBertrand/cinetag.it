import jwt
from flask_mail import Message
from flask import current_app, url_for
from datetime import datetime, timedelta
from app.extensions import mail


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
        {"user_id": user.id, "exp": datetime.utcnow() + timedelta(hours=24)},
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return token


def generate_password_reset_token(user):
    token = jwt.encode(
        {"reset_password": user.id, "exp": datetime.utcnow() + timedelta(hours=1)},
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return token


def send_confirmation_email(user):
    token = generate_confirmation_token(user)
    confirm_url = url_for("html.confirm_email", token=token, _external=True)
    subject = "Please confirm your email"
    body = (
        f"Hi {user.name},\n\nPlease click the link below to "
        f"confirm your email address:\n\n{confirm_url}\n\nThank you!"
    )
    send_email(user.email, subject, body)


def send_password_reset_email(user):
    token = generate_password_reset_token(user)
    reset_url = url_for("api.reset_password", token=token, _external=True)
    subject = "Password Reset Requested"
    body = (
        f"Hi {user.name},\n\nPlease click the link below "
        f"to reset your password:\n\n{reset_url}\n\nThank you!"
    )
    send_email(user.email, subject, body)
