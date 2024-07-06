from datetime import datetime, timedelta
from typing import Dict, List

import jwt
from babel.dates import format_date
from flask import current_app, url_for
from werkzeug.security import generate_password_hash

from app.extensions import db, bcrypt
from app.models import (
    User,
    UserMovie,
    Movie,
    MovieRegionInfo,
    MovieLanguageInfo,
    MiscData,
)
from app.services.movie_service import get_region_infos, get_lang_infos
from app.services.tmdb_service import sync_upcoming_movies
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
        if not user.new_email or user.new_email != data["new_mail"]:
            raise ValueError("Invalid token.")
        user.email = user.new_email
        user.new_email = None
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

    def fmt_date(date):
        return format_date(date, locale=lang) if date else None

    def get_region_info(mv):
        items = [ri for ri in mv.region_info if ri.region == region]
        if not items:
            items = [ri for ri in mv.region_info if ri.region == "US"]
        return items[0] if items else None

    def get_language_info(mv):
        items = [li for li in mv.language_info if li.language == lang]
        if not items or not items[0].overview or not items[0].poster_path:
            items = [li for li in mv.language_info if li.language == "en"]
        if not items or not items[0].overview or not items[0].poster_path:
            items = [
                li
                for li in mv.language_info
                if li.language == mv.original_language
            ]
        return items[0] if items else None

    # Sync upcoming movies from TMDb with the local database
    # will exit early if the last sync is recent enough
    last_query = MiscData.get("last_sync_upcoming_movies_%s" % region)
    if last_query:
        last_query = datetime.fromisoformat(last_query)
    if not last_query or (datetime.now() - last_query).total_seconds() > 86400:
        sync_upcoming_movies(region, lang)

    upcoming_movie_ids = {
        m.movie_id
        for m in MovieRegionInfo.query.filter_by(region=region).filter(
            MovieRegionInfo.release_date > datetime.now().date()
        )
    }

    if mode == "all":
        movie_ids = upcoming_movie_ids
    elif mode == "pending":
        movie_ids = upcoming_movie_ids - reviewed_movie_ids
    elif mode == "reviewed":
        movie_ids = reviewed_movie_ids & upcoming_movie_ids
    elif mode == "maybe":
        movie_ids = {
            um.movie_id for um in user_movies_query if um.decision == "maybe"
        }
        movie_ids &= upcoming_movie_ids
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

    movie_decisions = {um.movie_id: um.decision for um in user_movies_query}

    for movie in filtered_movies:
        region_info: MovieRegionInfo | None = get_region_info(movie)

        if (
            not region_info
            or not region_info.release_date
            or region_info.release_date < now
        ):
            continue

        lang_info: MovieLanguageInfo | None = get_language_info(movie)
        if not lang_info:
            # no data to display
            continue

        result.append(
            {
                "id": movie.id,
                "title": lang_info.title,
                "original_title": movie.original_title,
                "release_date": fmt_date(region_info.release_date),
                "release_date_raw": region_info.release_date,
                "overview": lang_info.overview,
                "poster_path": lang_info.poster_path,
                "popularity": movie.popularity,
                "decision": movie_decisions.get(movie.id),
            }
        )

    return sorted(result, key=lambda x: x["release_date_raw"])


def _get_user_movies(user, start: datetime = None, end: datetime = None):
    if not start or not end:
        return UserMovie.query.filter_by(user_id=user.id, decision="approve").all()
    if not start:
        start = datetime.min
    if not end:
        end = datetime.max

    joined_query = (
        db.session.query(UserMovie)
        .join(MovieRegionInfo, UserMovie.movie_id == MovieRegionInfo.movie_id)
        .filter(
            UserMovie.user_id == user.id,
            UserMovie.decision == "approve",
            MovieRegionInfo.region == user.region,
            MovieRegionInfo.release_date >= start,
            MovieRegionInfo.release_date <= end,
        )
    )
    return joined_query.all()


def fetch_user_events(
    user, start: datetime = None, end: datetime = None
) -> List[Dict[str, str]]:
    if not user:
        raise ValueError("User not found.")
    lang = user.language or current_app.config.DEFAULT_LANGUAGE
    region = user.region or current_app.config.DEFAULT_REGION

    def fmt_date(date):
        return format_date(date, locale=lang) if date else None

    approved_movies = _get_user_movies(user, start, end)
    movie_ids = [um.movie_id for um in approved_movies]
    lang_infos = get_lang_infos(movie_ids, lang)
    region_infos = get_region_infos(movie_ids, region)

    events = []
    for user_movie in approved_movies:
        lang_info = lang_infos.get(user_movie.movie_id)
        region_info = region_infos.get(user_movie.movie_id)
        if not lang_info or not region_info:
            continue

        start_datetime = datetime.combine(
            region_info.release_date, datetime.min.time()
        )

        events.append(
            {
                "title": lang_info.title,
                "start": start_datetime.isoformat(),
                "start_pretty": fmt_date(region_info.release_date),
                "sort_order": region_info.release_date,
                "url": url_for(
                    "html.get_movie_details", movie_id=user_movie.movie_id
                ),
                "allDay": True,
            }
        )
    return sorted(events, key=lambda x: x["sort_order"])
