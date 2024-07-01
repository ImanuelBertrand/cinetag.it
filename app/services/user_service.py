from flask import g
from flask_jwt_extended import (
    create_access_token,
    get_jwt_identity,
    verify_jwt_in_request,
)
from werkzeug.exceptions import Unauthorized
import logging
from app.models import db, User
from app.utils.email import send_confirmation_email


_logger = logging.getLogger(__name__)


def register_user(data):
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if User.query.filter_by(email=email).first():
        raise ValueError("Email already exists.")

    user = User(username=username, email=email, is_temporary=False)
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    send_confirmation_email(user)
    return user


def authenticate_user(data):
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if user and user.check_password(password):
        access_token = create_access_token(identity=user.id)
        return access_token
    else:
        raise Unauthorized("Invalid credentials.")


def confirm_user_email(token):
    # Implement token decoding and user email confirmation
    pass


def reset_user_password(token, new_password):
    # Implement password reset logic
    pass


def create_temporary_user() -> User:
    user = User(is_temporary=True)
    db.session.add(user)
    db.session.commit()
    return user


def get_current_user(allow_guest: bool = True) -> User | None:
    user_id = get_jwt_identity()
    _logger.info("User ID: %s", user_id)
    if user_id:
        user = User.query.get(user_id)
        if user:
            return user

    if allow_guest:
        return create_temporary_user()

    return None


def initialize_user(allow_guest: bool = True):
    try:
        verify_jwt_in_request(optional=True)
    except Exception as e:
        _logger.error("Error verifying JWT in request: %s", e)
        raise e
    g.current_user = get_current_user(allow_guest)
    return g.current_user
