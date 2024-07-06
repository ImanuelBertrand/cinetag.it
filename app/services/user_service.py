import logging

from crawlerdetect import CrawlerDetect
from flask import g, request
from flask_jwt_extended import (
    get_jwt_identity,
    verify_jwt_in_request,
)

from app.models import db, User
from app.utils.email import send_confirmation_email

_logger = logging.getLogger(__name__)


def register_user(data):
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if User.query.filter_by(email=email).first():
        raise ValueError("Email already exists.")

    user = User(username=username, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    send_confirmation_email(user)
    return user


def reset_user_password(token, new_password):
    # Implement password reset logic
    pass


def create_temporary_user() -> User:
    user = User()
    db.session.add(user)
    db.session.commit()
    return user


def get_current_user(allow_guest: bool = True) -> User | None:
    user_id = get_jwt_identity()
    if user_id:
        user = User.query.get(user_id)
        if user:
            return user

    if allow_guest:
        return create_temporary_user()

    return None


def is_bot() -> bool:
    return CrawlerDetect(request.headers).isCrawler()


def initialize_user(allow_guest: bool = True) -> User | None:
    if is_bot():
        _logger.info(
            "Bot detected, skipping user initialization: '%s', '%s'",
            request.remote_addr,
            request.headers.get("User-Agent"),
        )
        return None

    try:
        verify_jwt_in_request(optional=True)
    except Exception as e:
        _logger.error("Error verifying JWT in request: %s", e)
        raise e
    g.current_user = get_current_user(allow_guest)

    return g.current_user
