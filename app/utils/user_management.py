import math
from datetime import datetime, timedelta
from typing import Dict, List

import jwt
from babel.dates import format_date
from flask import current_app, url_for
from werkzeug.security import generate_password_hash, check_password_hash

from app.models import User, UserMovie, Movie, MovieRegionInfo
from app.services.movie_service import sync_upcoming_movies
from app.utils.email import send_email

from app.extensions import db, bcrypt


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


def authenticate_user(data) -> User:
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
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
        user = User.query.get(data["user_id"])
        if not user:
            raise KeyError("User not found.")
        user.email_confirmed = True
        user.is_temporary = False
        db.session.commit()
    except jwt.ExpiredSignatureError:
        raise ValueError("The confirmation link has expired.")
    except jwt.InvalidTokenError:
        raise ValueError("Invalid token.")


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


def get_movies_based_on_filter(user: User, mode: str) -> List[Dict[str, str]]:
    user_movies_query = UserMovie.query.filter_by(user_id=user.id)
    reviewed_movie_ids = {um.movie_id for um in user_movies_query}

    region = user.region or current_app.config.DEFAULT_REGION
    lang = user.language or current_app.config.DEFAULT_LANGUAGE
    lang_short = lang.split("-")[0]

    def fmt_date(date):
        return format_date(date, locale=lang_short) if date else None

    # Sync upcoming movies from TMDb with the local database
    upcoming_movie_ids = set(sync_upcoming_movies(region, lang))

    if mode == "pending":
        movie_ids = upcoming_movie_ids - reviewed_movie_ids
    elif mode == "reviewed":
        movie_ids = reviewed_movie_ids & upcoming_movie_ids
    elif mode == "approved":
        movie_ids = {
            um.movie_id for um in user_movies_query if um.decision == "approve"
        }
        movie_ids &= upcoming_movie_ids
    elif mode == "disapproved":
        movie_ids = {
            um.movie_id for um in user_movies_query if um.decision == "disapprove"
        }
        movie_ids &= upcoming_movie_ids
    else:
        raise ValueError("Invalid filter mode.")

    filtered_movies = Movie.query.filter(Movie.id.in_(movie_ids)).all()

    result = []
    now = datetime.now().date()
    for movie in filtered_movies:
        region_info: MovieRegionInfo = next(
            r for r in movie.region_info if r.region == region
        )
        if not region_info.release_date or region_info.release_date < now:
            continue
        lang_info = next(li for li in movie.language_info if li.language == lang)
        wait_days = (region_info.release_date - now).total_seconds() / 86400
        result.append(
            {
                "id": movie.id,
                "title": lang_info.title,
                "original_title": movie.original_title,
                "release_date": fmt_date(region_info.release_date),
                "wait_days": wait_days,
                "overview": lang_info.overview,
                "poster_path": lang_info.poster_path,
                "popularity": movie.popularity,
            }
        )

    def sort_func(item):
        weeks_till_release = item["wait_days"] / 7
        popularity = item["popularity"]
        return popularity * math.exp(-weeks_till_release)

    return sorted(result, key=sort_func, reverse=True)


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
