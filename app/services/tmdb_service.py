import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import natsort
from flask import current_app
from natsort import natsorted

from app.exceptions import TMDbAPIError
from app.extensions import db
from app.models.misc_data import MiscData
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.tmdb_language import TmdbLanguage
from app.models.tmdb_region import TmdbRegion
from app.models.user import User
from app.services.movie_service import get_lang_infos, get_region_infos
from app.utils.tmdb import (
    fetch_languages,
    fetch_regions,
    fetch_upcoming_movies,
    fetch_movie_languages,
    fetch_movie_images,
    fetch_release_dates,
    fetch_changed_movies,
    fetch_movie_details,
)

_logger = logging.getLogger(__name__)


def fetch_new_languages():
    api_languages = {language["iso_639_1"]: language for language in fetch_languages()}
    db_languages = {language.code: language for language in TmdbLanguage.query.all()}

    languages_to_delete = [code for code in db_languages if code not in api_languages]
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
    """
    Save a list of movies to the database.
    It will create the movie itself, but also the region and language info of the
    current call. Cron jobs will later update the language and region info for all
    regions and languages.
    :param tmdb_movies:
    :param region:
    :param language:
    :return:
    """
    movie_ids = [movie["id"] for movie in tmdb_movies]
    existing_movies: Dict[int, Movie] = {
        movie.id: movie for movie in Movie.query.filter(Movie.id.in_(movie_ids)).all()
    }
    existing_lang_info = get_lang_infos(movie_ids, language)
    existing_region_info = get_region_infos(movie_ids, region)

    movies_to_add: list[Movie] = []
    region_info_to_add: list[MovieRegionInfo] = []
    language_info_to_add: list[MovieLanguageInfo] = []

    for tmdb_movie in tmdb_movies:
        movie_id = tmdb_movie["id"]
        movie = existing_movies.get(tmdb_movie["id"])
        release_date = datetime.strptime(tmdb_movie["release_date"], "%Y-%m-%d").date()
        if not movie:
            movies_to_add.append(Movie.create_from_tmdb(tmdb_movie))
        elif movie.update_from_tmdb(tmdb_movie):
            db.session.add(movie)

        region_info: MovieRegionInfo = existing_region_info.get(movie_id)
        if not region_info:
            region_info_to_add.append(
                MovieRegionInfo.create_from_tmdb(movie_id, region, release_date)
            )
        elif region_info.update_from_tmdb(release_date):
            db.session.add(region_info)

        language_info: MovieLanguageInfo = existing_lang_info.get(movie_id)
        if not language_info:
            language_info_to_add.append(
                MovieLanguageInfo.create_from_tmdb(movie_id, tmdb_movie, language)
            )
        elif language_info.update_from_tmdb(tmdb_movie):
            db.session.add(language_info)

    if movies_to_add:
        db.session.bulk_save_objects(movies_to_add)
    if region_info_to_add:
        db.session.bulk_save_objects(region_info_to_add)
    if language_info_to_add:
        db.session.bulk_save_objects(language_info_to_add)


def sync_upcoming_movies(region: str, language: str = None) -> List[int]:
    """
    Fetch upcoming movies from TMDb and ensure they are stored in the database.
    """
    if language is None:
        language = "en"
    _logger.info(
        "Syncing upcoming movies for region %s and language %s", region, language
    )

    tmdb_movies = fetch_upcoming_movies(region, language)
    save_movie_list(tmdb_movies, region, language)

    MiscData.save("last_sync_upcoming_movies_%s" % region, datetime.now().isoformat())
    db.session.commit()

    _logger.info("Synced %s upcoming movies", len(tmdb_movies))
    return [movie["id"] for movie in tmdb_movies]


def update_movie_details(movie: Movie):
    movie_data = fetch_movie_details(movie.id, "en")
    if not movie_data:
        return

    movie.update_from_tmdb(movie_data)
    db.session.add(movie)


def update_movie_languages(movie: Movie):
    tmdb_movie_languages = fetch_movie_languages(movie.id)
    if not tmdb_movie_languages:
        return

    lang_dict = {lang["iso_639_1"]: lang for lang in tmdb_movie_languages}

    existing_lang_infos = MovieLanguageInfo.query.filter_by(movie_id=movie.id).all()
    existing_languages = {info.language for info in existing_lang_infos}

    lang_ids_to_delete = [
        info.id for info in existing_lang_infos if info.language not in lang_dict
    ]
    if lang_ids_to_delete:
        MovieLanguageInfo.query.filter(
            MovieLanguageInfo.id.in_(lang_ids_to_delete)
        ).delete()

    lang_infos_to_update = [
        info
        for info in existing_lang_infos
        if info.language in lang_dict
        and info.update_from_tmdb(lang_dict[info.language]["data"])
    ]
    db.session.add_all(lang_infos_to_update)

    new_languages = [
        lang["iso_639_1"]
        for lang in tmdb_movie_languages
        if lang["iso_639_1"] not in existing_languages
    ]

    # Deduplication of TMDB languages. TODO research, find better solution
    new_infos = {}
    for lang in new_languages:
        if lang in new_infos:
            continue
        new_infos[lang] = MovieLanguageInfo.create_from_tmdb(movie.id, lang_dict[lang])

    db.session.bulk_save_objects(new_infos.values())


def update_movie_posters(movie: Movie):
    language_infos = MovieLanguageInfo.query.filter_by(movie_id=movie.id).all()
    if not language_infos:
        return

    movie_images = fetch_movie_images(movie.id)
    if not movie_images:
        return

    posters = movie_images.get("posters", [])
    if not posters:
        return

    def get_lang(data):
        return data["iso_639_1"] or movie.original_language

    langs = {get_lang(p) for p in posters}
    lang_posters = {lang: [p for p in posters if get_lang(p) == lang] for lang in langs}

    best_posters = {
        lang: max(lang_posters[lang], key=lambda p: p["vote_average"]) for lang in langs
    }

    us_poster = best_posters.get("en") or next(iter(best_posters.values()), None)

    for lang_info in language_infos:
        poster = best_posters.get(lang_info.language) or us_poster
        if not poster:
            continue
        lang_info.poster_path = poster["file_path"]
        db.session.add(lang_info)


def fetch_theatrical_releases(movie: Movie) -> List[Dict[str, Any]]:
    filtered_regions = []
    for region_data in fetch_release_dates(movie.id):
        region_data["release_dates"] = [
            release for release in region_data["release_dates"] if release["type"] == 3
        ]
        if region_data["release_dates"]:
            filtered_regions.append(region_data)

    return filtered_regions


def update_movie_regions(movie: Movie) -> None:
    release_data = fetch_theatrical_releases(movie)
    if not release_data:
        MovieRegionInfo.query.filter_by(movie_id=movie.id).delete()
        return

    best_release_dates = {}
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    for data in release_data:
        region = data["iso_3166_1"]
        dates = data["release_dates"]
        pure_release_dates = [d for d in dates if not d["note"]]
        if pure_release_dates:
            date = min([d["release_date"] for d in pure_release_dates])
        else:
            date = min([d["release_date"] for d in dates])
        best_release_dates[region] = datetime.strptime(date, fmt).date()

    existing_region_infos = MovieRegionInfo.query.filter_by(movie_id=movie.id).all()

    # Create new objects that are missing in the db (not fake ones)
    existing_regions = {info.region for info in existing_region_infos}

    new_region_infos = {}
    for rd in best_release_dates:
        if rd in existing_regions or rd in new_region_infos:
            continue
        new_region_infos[rd] = MovieRegionInfo.create_from_tmdb(
            movie.id, rd, best_release_dates[rd]
        )
    db.session.bulk_save_objects(new_region_infos.values())

    # Update existing objects (remove fake flag if set previously)
    region_infos_to_update = [
        info for info in existing_region_infos if info.region in best_release_dates
    ]
    for region_info in region_infos_to_update:
        date = best_release_dates.get(region_info.region)
        if region_info.update_from_tmdb(date):
            db.session.add(region_info)

    # Delete non-fake region infos that are no longer in the theatrical releases
    region_infos_to_delete = [
        info
        for info in existing_region_infos
        if not info.is_fake and info.region not in best_release_dates
    ]
    for region_info in region_infos_to_delete:
        db.session.delete(region_info)

    # Create fake objects for regions that are missing in the DB
    original_release_date = min(best_release_dates.values())
    all_regions = TmdbRegion.query.all()
    missing_regions = (
        {region.code for region in all_regions}
        - existing_regions
        - set(new_region_infos.keys())
    )
    fake_region_infos = [
        MovieRegionInfo(
            movie_id=movie.id,
            region=region,
            release_date=original_release_date,
            is_fake=True,
        )
        for region in missing_regions
    ]
    if fake_region_infos:
        db.session.bulk_save_objects(fake_region_infos)

    # Update outdated fake objects
    fake_region_infos = MovieRegionInfo.query.filter(
        MovieRegionInfo.movie_id == movie.id,
        MovieRegionInfo.is_fake.is_(True),
        MovieRegionInfo.release_date != original_release_date,
    ).all()
    fake_ids_to_update = [info.id for info in fake_region_infos]
    if fake_ids_to_update:
        MovieRegionInfo.query.filter(MovieRegionInfo.id.in_(fake_ids_to_update)).update(
            {MovieRegionInfo.release_date: original_release_date}
        )


def _get_movie_info_update_threshold():
    return datetime.now() - timedelta(days=14)


def check_movie_information(movie: Movie):
    if not movie:
        return

    threshold = _get_movie_info_update_threshold()
    if movie.info_update_at and movie.info_update_at >= threshold:
        return

    try:
        update_movie_details(movie)
        update_movie_languages(movie)
        update_movie_posters(movie)
        update_movie_regions(movie)
        movie.info_update_at = datetime.now()
        db.session.add(movie)
    except TMDbAPIError as e:
        if e.status_code == 404:
            _logger.error("Movie %s not found on TMDb", movie)
            db.session.delete(movie)
        else:
            _logger.error("Error updating movie information for %s: %s", movie, e)
    except Exception:
        _logger.exception("Error updating movie information for %s", movie)


def update_all_upcoming_movies():
    _logger.info("Updating all upcoming movies")

    used_regions_by_users = db.session.query(User.region).distinct().all()
    used_regions_by_users = {region for (region,) in used_regions_by_users}
    used_regions_by_users = used_regions_by_users | {"US", "DE", "GB", "FR"}

    for region in used_regions_by_users:
        sync_upcoming_movies(region, "en")

    refresh_outdated_movies()


def refresh_changed_movies():
    last_refresh_date = MiscData.get("last_refresh_changes_movies")
    if not last_refresh_date:
        MiscData.save("last_refresh_changes_movies", datetime.now().isoformat())
        db.session.query(Movie).update(
            {Movie.info_update_at: None}, synchronize_session=False
        )
        db.session.commit()
        return

    start_date = datetime.fromisoformat(last_refresh_date).date()
    if start_date < datetime.now().date() - timedelta(days=14):
        start_date = datetime.now().date() - timedelta(days=14)
    end_date = datetime.now().date()
    if start_date >= end_date:
        # Would be nice to fetch intraday updates, but TMDB only supports dates
        # so this would lead to a lot of redundant updates.
        return
    changed_movie_ids = fetch_changed_movies(start_date, end_date)

    db.session.query(Movie).filter(Movie.id.in_(changed_movie_ids)).update(
        {Movie.info_update_at: None}, synchronize_session=False
    )

    MiscData.save("last_refresh_changes_movies", datetime.now().isoformat())


def refresh_outdated_movies():
    outdated_movies = Movie.query.filter(
        db.or_(
            Movie.info_update_at.is_(None),
            Movie.info_update_at < _get_movie_info_update_threshold(),
        )
    ).all()
    refresh_movie_information(outdated_movies)


def refresh_movie_information(movies: List[Movie]):
    _logger.info("Checking %s movies for updated information", len(movies))
    c = 0
    for movie in movies:
        try:
            check_movie_information(movie)
        except Exception:
            _logger.exception("Exception while checking movie information of %s", movie)
        c += 1
        if c % 10 == 0:
            db.session.commit()
    db.session.commit()
