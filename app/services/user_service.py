from datetime import datetime

from flask_jwt_extended import create_access_token
from werkzeug.exceptions import Unauthorized

from app.models import db, User
from app.utils.email import send_confirmation_email


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


def create_temporary_user():
    user = User(
        username="temp_" + str(datetime.utcnow().timestamp()),
        email="temp_" + str(datetime.utcnow().timestamp()) + "@example.com",
        is_temporary=True,
    )
    db.session.add(user)
    db.session.commit()
    return user
