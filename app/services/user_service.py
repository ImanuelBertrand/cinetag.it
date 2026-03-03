import logging
from collections import defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from babel.dates import format_date
from flask import current_app, g, url_for
from flask_sqlalchemy.session import Session
from sqlalchemy import func
from sqlalchemy.orm.exc import UnmappedInstanceError

from app.errors import UserFeedbackError
from app.extensions import bcrypt, cache, db
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
from app.utils.profiler import Profiler, profile_function

_logger = logging.getLogger(__name__)


def authenticate_user(data) -> User:
    email = data.get("email")
    password = data.get("password")

    user = User.query.filter_by(email=email).first()
    if not user or not bcrypt.check_password_hash(user.password, password):
        raise UserFeedbackError("Invalid email or password.")

    return user


def generate_confirmation_token(user):
    return jwt.encode(
        {"confirm": user.id, "exp": datetime.now(UTC) + timedelta(hours=24)},
        current_app.config["SECRET_KEY"],
        algorithm="HS256",
    )


def confirm_user_email(token):
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
        user = db.session.get(User, data["confirmation"])
        if not user:
            raise UserFeedbackError("User not found.")
        if not user.new_email or user.new_email != data["new_mail"]:
            raise UserFeedbackError("Invalid token.")
        user.email = user.new_email
        user.new_email = None
        db.session.commit()
    except jwt.ExpiredSignatureError:
        raise UserFeedbackError("The confirmation link has expired.") from None
    except jwt.InvalidTokenError:
        raise UserFeedbackError("Invalid token.") from None
    except KeyError:
        raise UserFeedbackError("Invalid token.") from None


def hash_password(password: str) -> str:
    return bcrypt.generate_password_hash(password).decode("utf-8")


def reset_user_password(token, new_password):
    try:
        data = jwt.decode(token, current_app.config["SECRET_KEY"], algorithms=["HS256"])
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
        raise UserFeedbackError("The reset link has expired.") from None
    except jwt.InvalidTokenError:
        raise UserFeedbackError("Invalid token.") from None


def get_region_flag(region: str) -> str | None:
    if len(region) != 2 or not region.isalpha():
        return None
    a_ord = ord("A")
    first_flag_char = chr(ord(region[0].upper()) - a_ord + 0x1F1E6)
    second_flag_char = chr(ord(region[1].upper()) - a_ord + 0x1F1E6)
    return first_flag_char + second_flag_char


def get_user_movie_ids(user: User, decision: str | None = None):
    user_movies_query = UserMovie.query.filter_by(user_id=user.id)

    if decision is not None:
        user_movies_query = user_movies_query.filter_by(decision=decision)

    return user_movies_query


@cache.cached(timeout=86400, key_prefix="get_all_tmdb_regions_data_dict")
def get_all_tmdb_regions_data_dict() -> dict[str, dict[str, Any]]:
    return {region.code: region.to_dict() for region in TmdbRegion.query.all()}


@cache.cached(timeout=86400, key_prefix="get_all_region_flags")
def get_all_region_flags() -> dict[str, str]:
    return {
        region_code: get_region_flag(region_code)
        for region_code in get_all_tmdb_regions_data_dict()
    }


def _build_movies_query(
    user: User,
    region: str,
    language: str,
    min_release_date,
    min_movie_id: int | None,
    need_imdb: bool,
    name_filter: str | None,
    mode: str,
):
    query = (
        db.session.query(Movie, MovieRegionInfo, UserMovie)
        .join(
            MovieRegionInfo,
            db.and_(
                MovieRegionInfo.movie_id == Movie.id,
                MovieRegionInfo.region == region,
            ),
        )
        .outerjoin(
            UserMovie,
            db.and_(UserMovie.movie_id == Movie.id, UserMovie.user_id == user.id),
        )
        .filter(MovieRegionInfo.release_date >= datetime.now(UTC).date())
    )

    # Apply pagination filter
    if min_release_date and min_movie_id:
        # If we have both release date and movie ID, use a composite filter
        # to avoid deadlock when multiple movies have the same release date
        query = query.filter(
            db.or_(
                MovieRegionInfo.release_date > min_release_date,
                db.and_(
                    MovieRegionInfo.release_date == min_release_date,
                    Movie.id > min_movie_id,
                ),
            )
        )
        query = query.filter(MovieRegionInfo.release_date >= min_release_date)
    elif min_release_date or min_movie_id:
        raise ValueError("min_release_date and min_movie_id can only be used together")

    # Apply other filters
    if need_imdb:
        query = query.filter(Movie.imdb_id.isnot(None))

    # Apply name filter to the SQL query
    if name_filter and name_filter.strip():
        name_filter_value = f"%{name_filter.lower()}%"
        query = query.join(
            MovieLangInfo,
            db.and_(
                MovieLangInfo.movie_id == Movie.id,
                MovieLangInfo.language == language,
            ),
            isouter=True,
        )
        query = query.filter(
            db.or_(
                func.lower(MovieLangInfo.title).like(name_filter_value),
                func.lower(Movie.original_title).like(name_filter_value),
            )
        )

    # Apply mode filters
    if mode != "all":
        if mode == "approved":
            query = query.filter(UserMovie.decision == "approve")
        elif mode == "disapproved":
            query = query.filter(UserMovie.decision == "disapprove")
        elif mode == "maybe":
            query = query.filter(UserMovie.decision == "maybe")
        elif mode == "pending":
            query = query.filter(UserMovie.movie_id.is_(None))
    return query


def _get_preloaded_movie_data(movie_ids, region, language):
    # Preload all necessary movie regions
    movie_regions_query = (
        db.session.query(MovieRegionInfo)
        .join(Movie, Movie.id == MovieRegionInfo.movie_id)
        .filter(MovieRegionInfo.movie_id.in_(movie_ids))
        .filter(not MovieRegionInfo.is_fake)
        .filter(
            db.or_(
                MovieRegionInfo.region == region,
                func.find_in_set(MovieRegionInfo.region, Movie.origin_country) > 0,
            )
        )
    )
    movie_regions_dict = defaultdict(set)
    for movie_region in movie_regions_query.all():
        movie_regions_dict[movie_region.movie_id].add(movie_region)

    # preload all necessary movie languages
    movie_languages_query = (
        db.session.query(MovieLangInfo)
        .join(Movie, Movie.id == MovieLangInfo.movie_id)
        .filter(MovieLangInfo.movie_id.in_(movie_ids))
        .filter(
            db.or_(
                MovieLangInfo.language == language,
                MovieLangInfo.language == Movie.original_language,
                MovieLangInfo.language == "en",
            )
        )
    )
    movie_languages_dict = defaultdict(dict)
    for mov_lang in movie_languages_query.all():
        movie_languages_dict[mov_lang.movie_id][mov_lang.language] = mov_lang

    return movie_regions_dict, movie_languages_dict


@profile_function
def get_movies_based_on_filter(
    user: User,
    mode: str,
    need_imdb: bool = False,
    need_poster: bool = False,
    name_filter: str | None = None,
    min_release_date=None,
    min_movie_id=None,
    limit: int = 20,
) -> dict[str, Any]:
    profiler = Profiler(f"get_movies_based_on_filter(mode={mode}, limit={limit})")
    profiler.start()

    profiler.start_section("initialization")
    region = user.region or current_app.config.DEFAULT_REGION
    language = user.language or current_app.config.DEFAULT_LANGUAGE

    formatted_dates = {}

    def fmt_date(date: datetime.date):
        if not date:
            return None

        cache_key = str(date)
        if cache_key not in formatted_dates:
            formatted_dates[cache_key] = format_date(date, locale=language)

        return formatted_dates[cache_key]

    profiler.start_section("query_building")
    query = _build_movies_query(
        user,
        region,
        language,
        min_release_date,
        min_movie_id,
        need_imdb,
        name_filter,
        mode,
    )

    # Order by release date for consistent pagination
    query = query.order_by(MovieRegionInfo.release_date, Movie.id)

    # Apply limit for pagination
    # (get one extra to check if there are more results)
    query = query.limit(limit + 1)

    # Execute the query
    profiler.start_section("query_execution")
    results = query.all()

    profiler.start_section("result_processing")
    has_more = len(results) > limit

    # Trim to the requested limit
    if has_more:
        results = results[:limit]

    profiler.start_section("movie_preprocessing")

    # Preload all necessary movie regions
    movie_ids = [r[0].id for r in results]

    movie_regions_dict, movie_languages_dict = _get_preloaded_movie_data(
        movie_ids, region, language
    )

    tmdb_regions_dict = get_all_tmdb_regions_data_dict()
    region_flag_dict = get_all_region_flags()

    result = []
    for movie_tuple in results:
        movie, main_region_info, user_movie = movie_tuple

        # Get language info
        lang_info = movie.get_localized_data(language, movie_languages_dict[movie.id])
        if not lang_info:
            continue

        if need_poster and not lang_info.get("poster_path"):
            continue

        all_release_dates = [
            {
                "region": ri.region,
                "region_info": tmdb_regions_dict.get(ri.region),
                "date": ri.release_date,
                "date_pretty": fmt_date(ri.release_date),
                "flag": region_flag_dict.get(ri.region),
            }
            for ri in movie_regions_dict[movie.id]
        ]

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
                "decision": user_movie.decision if user_movie else None,
                "all_release_dates": all_release_dates,
            }
        )

    # Get the next cursor value if there are more results
    profiler.start_section("pagination_metadata")
    next_release_date = None
    next_movie_id = None
    if has_more and result:
        next_release_date = result[-1]["release_date"]
        next_movie_id = result[-1]["id"]

    # Stop the profiler before returning
    profiler.stop()

    return {
        "movies": result,
        "next_release_date": (
            next_release_date.isoformat() if next_release_date else None
        ),
        "next_movie_id": next_movie_id,
        "has_more": has_more,
    }


def _get_user_movies(
    user,
    start: datetime | None = None,
    end: datetime | None = None,
    decisions: list[str] | None = None,
):
    if decisions is None:
        decisions = ["approve"]

    if not start and not end:
        return UserMovie.query.filter(
            UserMovie.user_id == user.id, UserMovie.decision.in_(decisions)
        ).all()
    if not start:
        start = datetime.min.replace(tzinfo=UTC)
    if not end:
        end = datetime.max.replace(tzinfo=UTC)

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
    user,
    start: datetime | None = None,
    end: datetime | None = None,
    external_urls: bool = False,
) -> list[dict[str, str]]:
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

        start_datetime = datetime.combine(region_info.release_date, datetime.min.time())

        movie = Movie.query.get(user_movie.movie_id)

        events.append(
            {
                "title": lang_info["title"] or movie.original_title,
                "start": start_datetime.isoformat(),
                "start_pretty": fmt_date(region_info.release_date),
                "sort_order": region_info.release_date,
                "url": url_for(
                    "html.get_movie_details",
                    movie_id=user_movie.movie_id,
                    _external=not external_urls,
                ),
                "allDay": True,
                "decision": user_movie.decision,
            }
        )
    return sorted(events, key=lambda x: x["sort_order"])


def get_current_user() -> User | None:
    """
    Retrieves the current user from Flask's g object.
    If the user object exists but is detached from the current session,
    it attempts to re-attach it before returning.
    Returns the User object or None.
    """
    user = g.get("current_user")

    if user and isinstance(user, User):  # Check if it's actually a User instance
        try:
            # Check if the instance is associated with the *current* session
            object_session = Session.object_session(user)

            # If not attached to any session OR attached to a different session
            if not object_session or object_session is not db.session:
                _logger.debug(
                    "User %s found in g but potentially detached. "
                    "Merging into current session.",
                    getattr(user, "id", "N/A"),
                )
                # Merge the instance back into the current session.
                # If the instance has been modified, this might raise issues,
                # but usually safe for just re-associating for lazy loads.
                user = db.session.merge(user)
        except UnmappedInstanceError:
            # Handle case where g.current_user might be something unexpected
            _logger.warning("g.current_user was not a mapped User instance.")
            return None  # Treat as no user
        except Exception:
            _logger.exception(
                "Error checking/re-attaching user session state for user %s",
                getattr(user, "id", "N/A"),
            )

    return user


def queue_confirmation_mail(user: User):
    rate_limits = {
        60: 1,
        300: 5,
        86400: 10,
    }
    now = datetime.now(UTC)

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
            raise UserFeedbackError("Too many confirmation mails sent to this address.")

    queue_email(user, "confirm")
