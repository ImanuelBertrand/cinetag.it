import logging
from datetime import datetime, timedelta
from typing import List

from flask import current_app
from natsort import natsorted

from app.extensions import db
from app.models import (
    TmdbLanguage,
    TmdbRegion,
    User,
    MovieLanguageInfo,
    Movie,
    MovieRegionInfo,
    MiscData,
)
from app.utils.tmdb import (
    fetch_languages,
    fetch_regions,
    fetch_upcoming_movies,
    fetch_movie_details,
)
import natsort

_logger = logging.getLogger(__name__)


def fetch_new_languages():
    api_languages = {
        language["iso_639_1"]: language for language in fetch_languages()
    }
    db_languages = {
        language.code: language for language in TmdbLanguage.query.all()
    }

    languages_to_delete = [
        code for code in db_languages if code not in api_languages
    ]
    if languages_to_delete:
        db.session.delete(languages_to_delete)

    new_languages = [
        TmdbLanguage.create_from_tmdb(api_languages[code])
        for code in api_languages
        if code not in db_languages
    ]
    db.session.bulk_save_objects(new_languages)

    for language in api_languages.values():
        if language["iso_639_1"] in db_languages:
            existing_language = db_languages[language["iso_639_1"]]
            if existing_language.update_from_tmdb(language):
                db.session.add(existing_language)

    db.session.commit()


def _sort_objects(objects, user_counts):
    for obj in objects:
        if obj.code not in user_counts:
            user_counts[obj.code] = 0

    # calculate the average and median of the user counts

    sorted_counts = sorted(user_counts.values())
    average = sum(sorted_counts) / len(sorted_counts)
    median = sorted_counts[len(sorted_counts) // 2]

    # select all objects that have more users than both the average and the median
    popular_choices = [
        lang
        for lang in objects
        if user_counts[lang.code] > average and user_counts[lang.code] > median
    ]

    # the biggest 5 of those will be showed first (alphabetically),
    # then the rest, also alphabetically
    popular_choices.sort(key=lambda o: user_counts[o.code], reverse=True)
    count_top_objects = current_app.config.get("COUNT_TOP_SELECT_OPTION", 5)
    top_objects = popular_choices[:count_top_objects]
    top_objects = natsorted(
        top_objects, alg=natsort.ns.LOCALE, key=lambda o: o.get_name()
    )
    objects = natsorted(objects, alg=natsort.ns.LOCALE, key=lambda o: o.get_name())

    # step = 10 to allow for re-ordering some objects later, e.g. browser language
    c = 10

    for obj in top_objects:
        obj.sort_order = c
        db.session.add(obj)
        c += 10

    c += 1000  # useful to detect the difference between top and other choices
    for obj in objects:
        if obj in top_objects:
            continue
        obj.sort_order = c
        db.session.add(obj)
        c += 10


def calculate_language_sort_orders():
    languages = TmdbLanguage.query.all()
    user_counts = (
        db.session.query(User.language, db.func.count(User.id))
        .group_by(User.language)
        .all()
    )
    lang_counts = {lang: count for lang, count in user_counts}
    _sort_objects(languages, lang_counts)


def update_languages():
    fetch_new_languages()
    calculate_language_sort_orders()
    db.session.commit()


def calculate_region_sort_orders():
    regions = TmdbRegion.query.all()
    user_counts = (
        db.session.query(User.region, db.func.count(User.id))
        .group_by(User.region)
        .all()
    )
    region_counts = {reg: count for reg, count in user_counts}
    _sort_objects(regions, region_counts)


def fetch_new_regions():
    api_regions = {region["iso_3166_1"]: region for region in fetch_regions()}
    db_regions = {region.code: region for region in TmdbRegion.query.all()}

    regions_to_delete = [code for code in db_regions if code not in api_regions]
    if regions_to_delete:
        db.session.delete(regions_to_delete)

    new_regions = [
        TmdbRegion(
            code=api_regions[code]["iso_3166_1"],
            english_name=api_regions[code]["english_name"],
            native_name=api_regions[code]["native_name"],
        )
        for code in api_regions
        if code not in db_regions
    ]
    db.session.bulk_save_objects(new_regions)

    for region in api_regions.values():
        if region["iso_3166_1"] in db_regions:
            existing_region = db_regions[region["iso_3166_1"]]
            if existing_region.update_from_tmdb(region):
                db.session.add(existing_region)


def update_regions():
    fetch_new_regions()
    calculate_region_sort_orders()
    db.session.commit()


def save_movie_list(tmdb_movies: List[dict], region: str, language: str):
    movie_ids = [movie["id"] for movie in tmdb_movies]
    existing_movies = {
        movie.id: movie
        for movie in Movie.query.filter(Movie.id.in_(movie_ids)).all()
    }
    existing_lang_info = {
        info.movie_id: info
        for info in MovieLanguageInfo.query.filter(
            MovieLanguageInfo.movie_id.in_(movie_ids),
            MovieLanguageInfo.language == language,
        ).all()
    }

    existing_region_info = {
        info.movie_id: info
        for info in MovieRegionInfo.query.filter(
            MovieRegionInfo.movie_id.in_(movie_ids),
            MovieRegionInfo.region == region,
        ).all()
    }

    movies_to_add: list[Movie] = []
    region_info_to_add: list[MovieRegionInfo] = []
    language_info_to_add: list[MovieLanguageInfo] = []

    for tmdb_movie in tmdb_movies:
        movie = existing_movies.get(tmdb_movie["id"])
        if not movie:
            movies_to_add.append(Movie.create_from_tmdb(tmdb_movie))
        elif movie.original_title != tmdb_movie["original_title"]:
            movie.original_title = tmdb_movie["original_title"]
            db.session.add(movie)

        region_info: MovieRegionInfo = existing_region_info.get(tmdb_movie["id"])
        if not region_info:
            region_info_to_add.append(
                MovieRegionInfo.create_from_tmdb(tmdb_movie, region)
            )
        elif region_info.update_from_tmdb(tmdb_movie):
            db.session.add(region_info)

        language_info: MovieLanguageInfo = existing_lang_info.get(tmdb_movie["id"])
        if not language_info:
            language_info_to_add.append(
                MovieLanguageInfo.create_from_tmdb(tmdb_movie, language)
            )
        elif language_info.update_from_tmdb(tmdb_movie):
            db.session.add(language_info)

    if movies_to_add:
        db.session.bulk_save_objects(movies_to_add)
    if region_info_to_add:
        db.session.bulk_save_objects(region_info_to_add)
    if language_info_to_add:
        db.session.bulk_save_objects(language_info_to_add)


def sync_upcoming_movies(region: str, language: str) -> None:
    """
    Fetch upcoming movies from TMDb and ensure they are stored in the database.

    Args:
        region (str): The region code to fetch upcoming movies for.
        language (str): The language code to fetch movies in.

    Returns:
        List[Movie]: A list of Movie objects.
    """
    last_update_key = f"upcoming_movies_last_update_{region}_{language}"
    last_update = MiscData.query.filter_by(key=last_update_key).first()
    if last_update:
        last_update_datetime = datetime.strptime(
            last_update.value, "%Y-%m-%d %H:%M:%S.%f"
        )
        if last_update_datetime > datetime.utcnow() - timedelta(hours=1):
            return

    save_movie_list(
        fetch_upcoming_movies(region, language),
        region,
        language,
    )

    MiscData.save(last_update_key, datetime.utcnow())

    db.session.commit()


def update_all_upcoming_movies():
    MovieRegionInfo.query.filter(MovieRegionInfo.is_fake).delete()

    used_region_language_combinations_by_users = (
        db.session.query(User.region, User.language)
        .filter(User.region.isnot(None), User.language.isnot(None))
        .distinct()
        .all()
    )

    if ("US", "en") not in used_region_language_combinations_by_users:
        used_region_language_combinations_by_users.append(("US", "en"))

    for region, language in used_region_language_combinations_by_users:
        sync_upcoming_movies(region, language)

    us_movie_releases = MovieRegionInfo.query.filter(
        MovieRegionInfo.region == "US"
    ).all()

    for region, language in used_region_language_combinations_by_users:
        MovieRegionInfo.query.filter(
            MovieRegionInfo.region == region, MovieRegionInfo.is_fake == True
        ).delete()
        region_move_ids = MovieRegionInfo.query.filter(
            MovieRegionInfo.region == region
        ).all()
        region_move_ids = [movie.movie_id for movie in region_move_ids]
        movie_list_to_save = []
        for movie in us_movie_releases:
            if movie.movie_id in region_move_ids:
                continue
            db.session.add(
                MovieRegionInfo(
                    movie_id=movie.movie_id,
                    region=region,
                    release_date=movie.release_date,
                    is_fake=True,
                )
            )
            movie_details = fetch_movie_details(movie.movie_id, language)
            movie_details["release_date"] = movie.release_date.strftime("%Y-%m-%d")
            movie_list_to_save.append(movie_details)
        save_movie_list(movie_list_to_save, region, language)

    db.session.commit()
