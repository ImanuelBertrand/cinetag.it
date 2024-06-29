from datetime import datetime, timedelta

import jwt
from flask import current_app, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from app.extensions import db
from app.models import User, UserMovie, Movie
from app.utils.email import send_email


def register_user(data):
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if User.query.filter(
        (User.username == username) | (User.email == email)
    ).first():
        raise KeyError("Username or email already exists.")

    hashed_password = generate_password_hash(password)
    user = User(username=username, email=email, password=hashed_password)
    db.session.add(user)
    db.session.commit()

    return user


def authenticate_user(data):
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if not user or not check_password_hash(user.password, password):
        raise ValueError("Invalid email or password.")

    return user


def generate_confirmation_token(user):
    token = jwt.encode(
        {"confirm": user.id, "exp": datetime.utcnow() + timedelta(hours=24)},
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return token


def confirm_user_email(token):
    try:
        data = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        user = User.query.get(data["confirm"])
        if not user:
            raise KeyError("User not found.")
        user.email_confirmed = True
        db.session.commit()
    except jwt.ExpiredSignatureError:
        raise ValueError("The confirmation link has expired.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token.")


def send_confirmation_email(user):
    token = generate_confirmation_token(user)
    confirm_url = url_for("api.confirm_email", token=token, _external=True)
    subject = "Please confirm your email"
    body = (
        f"Hi {user.username}, please click the link "
        f"to confirm your email: {confirm_url}"
    )
    send_email(user.email, subject, body)


def generate_password_reset_token(user):
    token = jwt.encode(
        {"reset_password": user.id, "exp": datetime.utcnow() + timedelta(hours=1)},
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )
    return token


def send_password_reset_email(user):
    token = generate_password_reset_token(user)
    reset_url = url_for("api.reset_password", token=token, _external=True)
    subject = "Password Reset Requested"
    body = (
        f"Hi {user.username}, please click the link "
        f"to reset your password: {reset_url}"
    )
    send_email(user.email, subject, body)


def reset_user_password(token, new_password):
    try:
        data = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        user = User.query.get(data["reset_password"])
        if not user:
            raise KeyError("User not found.")
        user.password = generate_password_hash(new_password)
        db.session.commit()
    except jwt.ExpiredSignatureError:
        raise ValueError("The reset link has expired.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token.")


def get_user_from_token(token):
    try:
        data = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        user = User.query.get(data["confirm"])
        if not user:
            raise KeyError("User not found.")
        return user
    except jwt.ExpiredSignatureError:
        raise ValueError("The token has expired.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token.")


def get_movies_based_on_filter(user_id, filter_mode):
    user = User.query.get(user_id)
    if not user:
        raise ValueError("User not found.")

    user_movies_query = UserMovie.query.filter_by(user_id=user_id)
    reviewed_movie_ids = {um.movie_id for um in user_movies_query}

    # Sync upcoming movies from TMDb with the local database
    upcoming_movies = Movie.get_upcoming_movies(
        region=user.region, language=user.language
    )
    upcoming_movie_ids = {movie.id for movie in upcoming_movies}

    if filter_mode == "pending":
        movie_ids = upcoming_movie_ids - reviewed_movie_ids
    elif filter_mode == "reviewed":
        movie_ids = reviewed_movie_ids & upcoming_movie_ids
    elif filter_mode == "approved":
        movie_ids = {
            um.movie_id for um in user_movies_query if um.decision == "approve"
        }
        movie_ids &= upcoming_movie_ids
    elif filter_mode == "disapproved":
        movie_ids = {
            um.movie_id for um in user_movies_query if um.decision == "disapprove"
        }
        movie_ids &= upcoming_movie_ids
    else:
        raise ValueError("Invalid filter mode.")

    filtered_movies = Movie.query.filter(Movie.id.in_(movie_ids)).all()

    return [
        {
            "id": movie.id,
            "title": movie.title,
            "release_date": movie.release_date,
            "overview": movie.overview,
        }
        for movie in filtered_movies
    ]


def fetch_user_calendar_events(user_id):
    approved_movies = UserMovie.query.filter_by(
        user_id=user_id, decision="approve"
    ).all()
    events = []
    for user_movie in approved_movies:
        movie = Movie.query.get(user_movie.movie_id)
        if movie:
            events.append(
                {
                    "title": movie.title,
                    "start": movie.release_date.strftime("%Y-%m-%d")
                    if movie.release_date
                    else None,
                    "description": movie.overview,
                }
            )
    return events
