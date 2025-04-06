import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List

import jwt
from babel.dates import format_date
from crawlerdetect import CrawlerDetect
from flask import current_app, url_for, request, g
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
from werkzeug.security import generate_password_hash

from app.exceptions import UserFeedbackError
from app.extensions import db, bcrypt
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo as MovieLangInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.send_confirmation_mails import (
    SentConfirmationMails as SentConfMails,
)
from app.models.tmdb_region import TmdbRegion
from app.models.user import User
from app.models.user_movie import UserMovie
from app.services.image_service import get_image_url
from app.services.movie_service import get_region_infos
from app.utils.email import queue_email

_logger = logging.getLogger(__name__)


def register_user(data):
    username = data.get("username")
    email = data.get("email")
    password = data.get("password")

    if User.query.filter(
        (User.username == username) | (User.email == email)
    ).first():
        raise UserFeedbackError("Username or email already exists.")

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
        raise UserFeedbackError("Invalid email or password.")

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
        user = User.query.get(data["confirmation"])
        if not user:
            raise UserFeedbackError("User not found.")
        if not user.new_email or user.new_email != data["new_mail"]:
            raise UserFeedbackError("Invalid token.")
        user.email = user.new_email
        user.new_email = None
        db.session.commit()
    except jwt.ExpiredSignatureError:
        raise UserFeedbackError("The confirmation link has expired.")
    except jwt.InvalidTokenError:
        raise UserFeedbackError("Invalid token.")


def hash_password(password: str) -> str:
    return bcrypt.generate_password_hash(password).decode("utf-8")


def reset_user_password(token, new_password):
    try:
        data = jwt.decode(
            token, current_app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        user_id = data.get("reset_password")
        reset_token = data.get("token")
        if not user_id or not reset_token:
            raise UserFeedbackError("Invalid reset token.")

        user = User.query.filter_by(
            id=user_id, password_reset_token=reset_token
        ).first()
        if not user:
            raise UserFeedbackError("Invalid reset token.")
        user.password = hash_password(new_password)
        user.password_reset_token = None
        db.session.add(user)
        db.session.commit()
    except jwt.ExpiredSignatureError:
        raise UserFeedbackError("The reset link has expired.")
    except jwt.InvalidTokenError:
        raise UserFeedbackError("Invalid token.")


def get_region_flag(region: str) -> str | None:
    if len(region) != 2 or not region.isalpha():
        return None
    a_ord = ord("A")
    first_flag_char = chr(ord(region[0].upper()) - a_ord + 0x1F1E6)
    second_flag_char = chr(ord(region[1].upper()) - a_ord + 0x1F1E6)
    return first_flag_char + second_flag_char


def get_movie_list_query(
    region: TmdbRegion,
    need_imdb: bool,
    need_poster: bool,
    user: User = None,
    user_decision: str = None,
):
    upcoming_movie_query = Movie.query.join(
        MovieRegionInfo,
        db.and_(
            MovieRegionInfo.region == region, MovieRegionInfo.movie_id == Movie.id
        ),
    ).filter(MovieRegionInfo.release_date > datetime.now().date())

    if need_imdb:
        upcoming_movie_query = upcoming_movie_query.filter(
            Movie.imdb_id.isnot(None)
        )

    if need_poster:
        poster_subquery = db.exists().where(
            db.and_(
                MovieLangInfo.movie_id == MovieRegionInfo.movie_id,
                MovieLangInfo.poster_path.isnot(None),
            )
        )
        upcoming_movie_query = upcoming_movie_query.filter(poster_subquery)

    if user is not None:
        # if user_decision is None, we filter for untagged movies,
        # so we need an outer join
        is_outer = user_decision is None

        upcoming_movie_query = upcoming_movie_query.join(
            UserMovie,
            db.and_(UserMovie.user_id == user.id, UserMovie.movie_id == Movie.id),
            isouter=is_outer,
        )

        if user_decision is None:
            upcoming_movie_query = upcoming_movie_query.filter(
                UserMovie.id.is_(None)
            )
        else:
            upcoming_movie_query = upcoming_movie_query.filter(
                UserMovie.decision == user_decision
            )

    return upcoming_movie_query


def get_user_movie_ids(user: User, decision: str = None):
    user_movies_query = UserMovie.query.filter_by(user_id=user.id)

    if decision is not None:
        user_movies_query = user_movies_query.filter_by(decision=decision)

    return user_movies_query


def get_movies_based_on_filter(
    user: User, mode: str, need_imdb: bool = False, need_poster: bool = False
) -> List[Dict[str, str]]:
    region = user.region or current_app.config.DEFAULT_REGION
    language = user.language or current_app.config.DEFAULT_LANGUAGE

    def fmt_date(date):
        return format_date(date, locale=language) if date else None

    filter_user = None
    filter_decision = None
    if mode != "all":
        filter_user = user
        if mode == "approved":
            filter_decision = "approve"
        if mode == "disapproved":
            filter_decision = "disapprove"
        if mode == "maybe":
            filter_decision = "maybe"

    filtered_movies = get_movie_list_query(
        region, need_imdb, need_poster, filter_user, filter_decision
    )
    movie_ids = {m.id for m in filtered_movies}

    user_movies_query = UserMovie.query.filter(
        db.and_(UserMovie.user_id == user.id, UserMovie.movie_id.in_(movie_ids))
    )
    movie_decisions = {um.movie_id: um.decision for um in user_movies_query}

    langs = MovieLangInfo.query.filter(MovieLangInfo.movie_id.in_(movie_ids)).all()
    language_dict = defaultdict(dict)
    for movie_lang in langs:
        language_dict[movie_lang.movie_id][movie_lang.language] = movie_lang

    region_infos = MovieRegionInfo.query.filter(
        MovieRegionInfo.movie_id.in_(movie_ids)
    ).all()
    region_info_dict = defaultdict(dict)
    for reg_info in region_infos:
        region_info_dict[reg_info.movie_id][reg_info.region] = reg_info

    tmdb_regions = TmdbRegion.query.all()
    tmdb_regions_dict = {r.code: r for r in tmdb_regions}

    now = datetime.now().date()
    result = []
    for movie in filtered_movies:
        rg_infos = region_info_dict.get(movie.id, {})
        origin_countries = movie.origin_country.split(",")
        main_region_info = rg_infos.get(region) or rg_infos.get("US")
        if not main_region_info:
            main_region_info = next(
                (rg_infos.get(c) for c in origin_countries if rg_infos.get(c)),
                None,
            )

        if (
            not main_region_info
            or not main_region_info.release_date
            or main_region_info.release_date < now
        ):
            continue

        relevant_regions = list({region} | set(origin_countries))
        all_release_dates = [
            {
                "region": r,
                "region_info": tmdb_regions_dict.get(r).to_dict(),
                "date": rg_infos.get(r).release_date,
                "date_pretty": fmt_date(rg_infos.get(r).release_date),
                "flag": get_region_flag(r),
            }
            for r in relevant_regions
            if rg_infos.get(r) and not rg_infos.get(r).is_fake
        ]

        lang_info = movie.get_localized_data(language, language_dict[movie.id])
        if not lang_info:
            continue

        if need_poster and not lang_info.get("poster_path"):
            continue

        result.append(
            {
                "id": movie.id,
                "title": lang_info["title"],
                "original_title": movie.original_title,
                "release_date_pretty": fmt_date(main_region_info.release_date),
                "release_date": main_region_info.release_date,
                "overview": lang_info["overview"],
                "poster_url": get_image_url(lang_info["poster_path"], 500),
                "popularity": movie.popularity,
                "decision": movie_decisions.get(movie.id),
                "all_release_dates": all_release_dates,
            }
        )

    return sorted(result, key=lambda x: x["release_date"])


def _get_user_movies(
    user, start: datetime = None, end: datetime = None, decisions: List[str] = None
):
    if decisions is None:
        decisions = ["approve"]

    if not start and not end:
        return UserMovie.query.filter(
            UserMovie.user_id == user.id, UserMovie.decision.in_(decisions)
        ).all()
    if not start:
        start = datetime.min
    if not end:
        end = datetime.max

    joined_query = (
        db.session.query(UserMovie)
        .join(MovieRegionInfo, UserMovie.movie_id == MovieRegionInfo.movie_id)
        .filter(
            UserMovie.user_id == user.id,
            UserMovie.decision.in_(decisions),
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

    approved_movies = _get_user_movies(user, start, end, ["approve", "maybe"])
    movie_ids = [um.movie_id for um in approved_movies]
    region_infos = get_region_infos(movie_ids, region)

    # prepare language infos to reduce queries
    all_lang_infos = MovieLangInfo.query.filter(
        MovieLangInfo.movie_id.in_(movie_ids)
    ).all()

    lang_info_dict = defaultdict(dict)
    for lang_info in all_lang_infos:
        lang_info_dict[lang_info.movie_id][lang_info.language] = lang_info

    events = []
    for user_movie in approved_movies:
        lang_info = user_movie.movie.get_localized_data(
            lang, lang_info_dict[user_movie.movie_id]
        )
        region_info = region_infos.get(user_movie.movie_id)
        if not lang_info or not region_info:
            continue

        start_datetime = datetime.combine(
            region_info.release_date, datetime.min.time()
        )

        movie = Movie.query.get(user_movie.movie_id)

        events.append(
            {
                "title": lang_info["title"] or movie.original_title,
                "start": start_datetime.isoformat(),
                "start_pretty": fmt_date(region_info.release_date),
                "sort_order": region_info.release_date,
                "url": url_for(
                    "html.get_movie_details", movie_id=user_movie.movie_id
                ),
                "allDay": True,
                "decision": user_movie.decision,
            }
        )
    return sorted(events, key=lambda x: x["sort_order"])


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
        g.current_user = get_current_user(allow_guest)
    except Exception as e:
        _logger.error("Error verifying JWT in request: %s", e)
        g.current_user = create_temporary_user()

    return g.current_user


def queue_confirmation_mail(user: User):
    rate_limits = {
        60: 1,
        300: 5,
        86400: 10,
    }
    now = datetime.utcnow()

    # Delete historic entries
    longest_duration = max(rate_limits.keys())
    threshold = now - timedelta(seconds=longest_duration)
    SentConfMails.query.filter(SentConfMails.sent_at < threshold).delete()

    # Check if we sent mails to this address before
    already_sent_mails = SentConfMails.query.filter_by(email=user.new_email).all()
    mails_sent_in_seconds = [
        (now - mail.sent_at).total_seconds() for mail in already_sent_mails
    ]

    # If so, check how often to avoid abuse
    for seconds, limit in rate_limits.items():
        if sum(1 for s in mails_sent_in_seconds if s < seconds) >= limit:
            raise UserFeedbackError(
                "Too many confirmation mails sent to this address."
            )

    queue_email(user, "confirm")
