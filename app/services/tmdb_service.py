import http
import logging
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

import natsort
from flask import current_app
from natsort import natsorted

from app.errors import TMDbAPIError
from app.extensions import db
from app.models.misc_data import MiscData
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.tmdb_genre import MovieGenre, TmdbGenre, TmdbGenreName
from app.models.tmdb_language import TmdbLanguage
from app.models.tmdb_region import TmdbRegion
from app.models.user import User
from app.services.image_service import delete_local_poster, prefetch_poster
from app.services.movie_service import get_lang_infos, get_region_infos
from app.utils.tmdb import (
    fetch_changed_movies,
    fetch_genre_list,
    fetch_languages,
    fetch_movie_details,
    fetch_movie_images,
    fetch_movie_languages,
    fetch_regions,
    fetch_release_dates,
    fetch_upcoming_movies,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

_logger = logging.getLogger(__name__)


def sync_genre_names(language: str) -> None:
    """Upsert TMDb genres and their localized names for the given language."""
    genres = fetch_genre_list(language)
    if not genres:
        return

    now = datetime.now(UTC)
    genre_ids = [g["id"] for g in genres]

    # Ensure base genres exist
    existing_genres = {
        g.id: g for g in TmdbGenre.query.filter(TmdbGenre.id.in_(genre_ids)).all()
    }
    new_genres = [
        TmdbGenre(id=gid, updated_at=now)
        for gid in genre_ids
        if gid not in existing_genres
    ]
    if new_genres:
        db.session.bulk_save_objects(new_genres)

    # Upsert names for this language
    existing_names = {
        (n.genre_id, n.language): n
        for n in (
            TmdbGenreName.query.filter(
                TmdbGenreName.genre_id.in_(genre_ids),
                TmdbGenreName.language == language,
            ).all()
        )
    }

    names_to_add = []
    for g in genres:
        key = (g["id"], language)
        existing = existing_names.get(key)
        if existing:
            if existing.name != g["name"]:
                existing.name = g["name"]
                existing.updated_at = now
                db.session.add(existing)
        else:
            names_to_add.append(
                TmdbGenreName(
                    genre_id=g["id"], language=language, name=g["name"], updated_at=now
                )
            )

    if names_to_add:
        db.session.bulk_save_objects(names_to_add)

    # Update updated_at on base genres
    if existing_genres:
        for gid in genre_ids:
            gen = existing_genres.get(gid)
            if gen and gen.updated_at != now:
                gen.updated_at = now
                db.session.add(gen)


def update_movie_genres(movie_id: int, tmdb_movie: dict) -> list[MovieGenre]:
    """Reconcile movie_genres rows for a movie from either list payload (genre_ids)
    or details payload (genres objects)."""
    if not tmdb_movie:
        return []

    if "genre_ids" in tmdb_movie and isinstance(tmdb_movie.get("genre_ids"), list):
        desired_ids = {int(gid) for gid in tmdb_movie.get("genre_ids", [])}
    elif "genres" in tmdb_movie and isinstance(tmdb_movie.get("genres"), list):
        desired_ids = {
            int(g.get("id")) for g in tmdb_movie.get("genres", []) if "id" in g
        }
    else:
        desired_ids = set()

    existing_links = MovieGenre.query.filter_by(movie_id=movie_id).all()
    existing_ids = {link.genre_id for link in existing_links}

    to_add = desired_ids - existing_ids
    to_delete = existing_ids - desired_ids

    if not desired_ids and not existing_ids:
        return []

    if to_delete:
        MovieGenre.query.filter(
            MovieGenre.movie_id == movie_id, MovieGenre.genre_id.in_(list(to_delete))
        ).delete(synchronize_session=False)

    # Ensure base genres exist for any new ids
    if to_add:
        existing_base = {
            g.id for g in TmdbGenre.query.filter(TmdbGenre.id.in_(list(to_add))).all()
        }
        missing = to_add - existing_base
        if missing:
            db.session.bulk_save_objects([TmdbGenre(id=gid) for gid in missing])

        return [MovieGenre(movie_id=movie_id, genre_id=gid) for gid in to_add]

    return []


def fetch_new_languages() -> None:
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


def _sort_objects(objects, user_counts) -> None:
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


def calculate_language_sort_orders() -> None:
    languages = TmdbLanguage.query.all()
    user_counts = (
        db.session.query(User.language, db.func.count(User.id))
        .group_by(User.language)
        .all()
    )
    lang_counts = {row[0]: row[1] for row in user_counts}
    _sort_objects(languages, lang_counts)


def update_languages() -> None:
    fetch_new_languages()
    calculate_language_sort_orders()
    db.session.commit()


def calculate_region_sort_orders() -> None:
    regions = TmdbRegion.query.all()
    user_counts = (
        db.session.query(User.region, db.func.count(User.id))
        .group_by(User.region)
        .all()
    )

    region_counts = {row[0]: row[1] for row in user_counts}
    _sort_objects(regions, region_counts)


def fetch_new_regions() -> None:
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


def update_regions() -> None:
    fetch_new_regions()
    calculate_region_sort_orders()
    db.session.commit()


def _process_movie(
    tmdb_movie: dict,
    existing_movies: dict[int, Movie],
    existing_region_info: dict[int, MovieRegionInfo],
    existing_lang_info: dict[int, MovieLanguageInfo],
    region: str,
    language: str,
) -> tuple[
    Movie | None, MovieRegionInfo | None, MovieLanguageInfo | None, list[MovieGenre]
]:
    movie_id = tmdb_movie["id"]
    movie = existing_movies.get(movie_id)
    if not tmdb_movie.get("release_date"):
        return None, None, None, []
    release_date = (
        datetime.strptime(tmdb_movie["release_date"], "%Y-%m-%d")
        .replace(tzinfo=UTC)
        .date()
    )

    res_movie = None
    if not movie:
        res_movie = Movie.create_from_tmdb(tmdb_movie)
    elif movie.update_from_tmdb(tmdb_movie):
        db.session.add(movie)

    res_region_info = None
    region_info = existing_region_info.get(movie_id)
    if not region_info:
        res_region_info = MovieRegionInfo.create_from_tmdb(
            movie_id, region, release_date
        )
    elif region_info.update_from_tmdb(release_date):
        db.session.add(region_info)

    res_language_info = None
    language_info = existing_lang_info.get(movie_id)
    if not language_info:
        res_language_info = MovieLanguageInfo.create_from_tmdb(
            movie_id, tmdb_movie, language
        )
    elif language_info.update_from_tmdb(tmdb_movie):
        db.session.add(language_info)

    res_genre_relations = []
    try:
        res_genre_relations = update_movie_genres(movie_id, tmdb_movie)
    except Exception:
        _logger.exception("Failed updating genres for movie %s", movie_id)

    return res_movie, res_region_info, res_language_info, res_genre_relations


def _bulk_save_movies(
    movies_to_add: list[Movie],
    region_info_to_add: list[MovieRegionInfo],
    language_info_to_add: list[MovieLanguageInfo],
    genre_relations_to_save: list[MovieGenre],
) -> None:
    if movies_to_add:
        db.session.bulk_save_objects(movies_to_add)
    if region_info_to_add:
        db.session.bulk_save_objects(region_info_to_add)
    if language_info_to_add:
        db.session.bulk_save_objects(language_info_to_add)
    if genre_relations_to_save:
        db.session.bulk_save_objects(genre_relations_to_save)


def save_movie_list(tmdb_movies: list[dict], region: str, language: str) -> None:
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
    # Ensure genre names for this language are synced (best-effort)
    try:
        sync_genre_names(language)
    except Exception:
        _logger.exception("Failed to sync genre names for language %s", language)

    movie_ids = [movie["id"] for movie in tmdb_movies]
    existing_movies: dict[int, Movie] = {
        movie.id: movie for movie in Movie.query.filter(Movie.id.in_(movie_ids)).all()
    }
    existing_lang_info = get_lang_infos(movie_ids, language)
    existing_region_info = get_region_infos(movie_ids, region)

    movies_to_add: list[Movie] = []
    region_info_to_add: list[MovieRegionInfo] = []
    language_info_to_add: list[MovieLanguageInfo] = []
    genre_relations_to_save: list[MovieGenre] = []

    for tmdb_movie in tmdb_movies:
        (
            m_to_add,
            ri_to_add,
            li_to_add,
            gr_to_add,
        ) = _process_movie(
            tmdb_movie,
            existing_movies,
            existing_region_info,
            existing_lang_info,
            region,
            language,
        )
        if m_to_add:
            movies_to_add.append(m_to_add)
        if ri_to_add:
            region_info_to_add.append(ri_to_add)
        if li_to_add:
            language_info_to_add.append(li_to_add)
        if gr_to_add:
            genre_relations_to_save += gr_to_add

    _bulk_save_movies(
        movies_to_add,
        region_info_to_add,
        language_info_to_add,
        genre_relations_to_save,
    )


def sync_upcoming_movies(region: str, language: str | None = None) -> list[int]:
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

    MiscData.save(f"last_sync_upcoming_movies_{region}", datetime.now(UTC).isoformat())
    db.session.commit()

    _logger.info("Synced %s upcoming movies", len(tmdb_movies))
    return [movie["id"] for movie in tmdb_movies]


def update_movie_details(movie: Movie) -> None:
    movie_data = fetch_movie_details(movie.id, "en")
    if not movie_data:
        return

    movie.update_from_tmdb(movie_data)
    db.session.add(movie)

    # Sync English genre names and update movie genre associations from details payload
    try:
        update_movie_genres(movie.id, movie_data)
    except Exception:
        _logger.exception("Failed syncing/updating genres for movie %s", movie.id)


def update_movie_languages(movie: Movie) -> None:
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


def update_movie_posters(movie: Movie) -> None:
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

    replaced_paths: set[str] = set()
    new_paths: set[str] = set()
    for lang_info in language_infos:
        poster: dict[str, Any] | None = (
            best_posters.get(lang_info.language) or us_poster
        )
        if not poster:
            continue
        new_path = poster["file_path"]
        if lang_info.poster_path != new_path:
            if lang_info.poster_path:
                replaced_paths.add(lang_info.poster_path)
            lang_info.poster_path = new_path
            db.session.add(lang_info)
        new_paths.add(new_path)

    _refresh_local_poster_cache(replaced_paths, new_paths)


def _refresh_local_poster_cache(replaced_paths: set[str], new_paths: set[str]) -> None:
    """Drop locally cached files for stale paths and prefetch the new ones.

    A "stale" poster is one whose TMDB file_path has changed — TMDB uses
    content-addressed paths, so the old local file is now unreachable. We still
    confirm no other lang_info references the path before deleting.
    """
    orphan_paths = replaced_paths - new_paths
    if orphan_paths:
        still_referenced = {
            path
            for (path,) in db.session.query(MovieLanguageInfo.poster_path)
            .filter(MovieLanguageInfo.poster_path.in_(orphan_paths))
            .distinct()
            .all()
        }
        for path in orphan_paths - still_referenced:
            delete_local_poster(path)

    for path in new_paths:
        prefetch_poster(path)


def fetch_theatrical_releases(movie: Movie) -> list[dict[str, Any]]:
    filtered_regions = []
    for region_data in fetch_release_dates(movie.id):
        region_data["release_dates"] = [
            release for release in region_data["release_dates"] if release["type"] == 3
        ]
        if region_data["release_dates"]:
            filtered_regions.append(region_data)

    return filtered_regions


def _parse_best_release_dates(
    release_data: list[dict[str, Any]],
) -> dict[str, date]:
    """
    Parses the raw API release data into a clean dict of {region: best_date}.
    """
    best_release_dates = {}
    fmt = "%Y-%m-%dT%H:%M:%S.%fZ"
    for data in release_data:
        region = data["iso_3166_1"]
        dates = data["release_dates"]

        # Prefer "pure" release dates (those without a 'note')
        pure_release_dates = [d["release_date"] for d in dates if not d["note"]]

        if pure_release_dates:
            date_str = min(pure_release_dates)
        elif dates:  # Fallback to using any date if no "pure" ones exist
            date_str = min(d["release_date"] for d in dates)
        else:
            continue  # Skip region if no dates are provided

        best_release_dates[region] = (
            datetime.strptime(date_str, fmt).replace(tzinfo=UTC).date()
        )
    return best_release_dates


def _create_new_region_infos(
    movie_id: int,
    best_release_dates: dict[str, date],
    existing_regions: set[str],
) -> set[str]:
    new_region_infos = []
    new_regions = set()
    for region, release_date in best_release_dates.items():
        if region in existing_regions or region in new_region_infos:
            continue
        new_region_infos.append(
            MovieRegionInfo.create_from_tmdb(movie_id, region, release_date)
        )
        new_regions.add(region)

    if new_region_infos:
        db.session.bulk_save_objects(new_region_infos)

    return new_regions


def _update_existing_region_infos(
    existing_region_infos: Sequence[MovieRegionInfo],
    best_release_dates: dict[str, date],
) -> None:
    """Updates existing region infos with new dates and removes 'is_fake' flag."""
    for region_info in existing_region_infos:
        release_date = best_release_dates.get(region_info.region)
        if release_date and region_info.update_from_tmdb(release_date):
            db.session.add(region_info)


def _delete_obsolete_region_infos(
    existing_region_infos: Sequence[MovieRegionInfo],
    best_release_dates: dict[str, date],
) -> None:
    """Deletes non-fake region infos that are no longer in the API data."""
    for region_info in existing_region_infos:
        if not region_info.is_fake and region_info.region not in best_release_dates:
            db.session.delete(region_info)


def _sync_fake_region_infos(
    movie_id: int,
    original_release_date: date,
    existing_regions: set[str],
    new_regions: set[str],
) -> None:
    # 1. Create missing fake objects
    all_regions = {region.code for region in TmdbRegion.query.all()}
    regions_needing_fakes = all_regions - existing_regions - new_regions
    fake_region_infos = [
        MovieRegionInfo(
            movie_id=movie_id,
            region=region,
            release_date=original_release_date,
            is_fake=True,
        )
        for region in regions_needing_fakes
    ]
    if fake_region_infos:
        db.session.bulk_save_objects(fake_region_infos)

    # 2. Update outdated fake objects
    fake_ids_to_update = [
        info.id
        for info in MovieRegionInfo.query.filter(
            MovieRegionInfo.movie_id == movie_id,
            MovieRegionInfo.is_fake.is_(True),
            MovieRegionInfo.release_date != original_release_date,
        ).all()
    ]

    if fake_ids_to_update:
        MovieRegionInfo.query.filter(MovieRegionInfo.id.in_(fake_ids_to_update)).update(
            {MovieRegionInfo.release_date: original_release_date}
        )


def update_movie_regions(movie: Movie) -> None:
    release_data = fetch_theatrical_releases(movie)
    if not release_data:
        MovieRegionInfo.query.filter_by(movie_id=movie.id).delete()
        return

    best_release_dates = _parse_best_release_dates(release_data)

    existing_region_infos = MovieRegionInfo.query.filter_by(movie_id=movie.id).all()
    existing_regions = {info.region for info in existing_region_infos}

    # Create new objects that are missing in the db (not fake ones)
    new_regions = _create_new_region_infos(
        movie.id, best_release_dates, existing_regions
    )

    # Update existing objects (remove fake flag if set previously)
    _update_existing_region_infos(existing_region_infos, best_release_dates)

    # Delete non-fake region infos that are no longer in the theatrical releases
    _delete_obsolete_region_infos(existing_region_infos, best_release_dates)

    # Handle fake release dates
    original_release_date = min(best_release_dates.values())
    _sync_fake_region_infos(
        movie.id, original_release_date, existing_regions, new_regions
    )


def _get_movie_info_update_threshold():
    return datetime.now(UTC) - timedelta(days=14)


def check_movie_information(movie: Movie) -> None:
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
        movie.info_update_at = datetime.now(UTC)
        db.session.add(movie)
    except TMDbAPIError as e:
        if e.status_code == http.HTTPStatus.NOT_FOUND:
            _logger.exception("Movie %s not found on TMDb", movie)
            db.session.delete(movie)
        else:
            _logger.exception("Error updating movie information for %s", movie)
    except Exception:
        _logger.exception("Error updating movie information for %s", movie)


def update_all_upcoming_movies() -> None:
    _logger.info("Updating all upcoming movies")

    used_regions_by_users = db.session.query(User.region).distinct().all()
    used_regions_by_users = {region for (region,) in used_regions_by_users if region}
    used_regions_by_users = used_regions_by_users | {"US", "DE", "GB", "FR"}

    sync_genre_names("en")

    for region in used_regions_by_users:
        sync_upcoming_movies(region, "en")

    refresh_outdated_movies()


def refresh_changed_movies() -> None:
    last_refresh_date = MiscData.get("last_refresh_changes_movies")
    if not last_refresh_date:
        MiscData.save("last_refresh_changes_movies", datetime.now(UTC).isoformat())
        db.session.query(Movie).update(
            {Movie.info_update_at: None}, synchronize_session=False
        )
        db.session.commit()
        return

    start_date = max(
        datetime.fromisoformat(last_refresh_date).date(),
        datetime.now(UTC).date() - timedelta(days=14),
    )
    end_date = datetime.now(UTC).date()
    if start_date >= end_date:
        # Would be nice to fetch intraday updates, but TMDB only supports dates
        # so this would lead to a lot of redundant updates.
        return
    changed_movie_ids = fetch_changed_movies(start_date, end_date)

    db.session.query(Movie).filter(Movie.id.in_(changed_movie_ids)).update(
        {Movie.info_update_at: None}, synchronize_session=False
    )

    MiscData.save("last_refresh_changes_movies", datetime.now(UTC).isoformat())


def refresh_outdated_movies() -> None:
    outdated_movies = Movie.query.filter(
        db.or_(
            Movie.info_update_at.is_(None),
            Movie.info_update_at < _get_movie_info_update_threshold(),
        )
    ).all()
    refresh_movie_information(outdated_movies)


def refresh_movie_information(movies: list[Movie]) -> None:
    _logger.info("Checking %s movies for updated information", len(movies))
    for c, movie in enumerate(movies):
        try:
            check_movie_information(movie)
        except Exception:
            _logger.exception("Exception while checking movie information of %s", movie)
        if c % 10 == 0:
            db.session.commit()
    db.session.commit()
