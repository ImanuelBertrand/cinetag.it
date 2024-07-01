from typing import List

from app.models import db, Movie, MovieRegionInfo, MovieLanguageInfo
from app.utils.tmdb import fetch_upcoming_movies


def sync_upcoming_movies(region: str, language: str) -> List[int]:
    """
    Fetch upcoming movies from TMDb and ensure they are stored in the database.

    Args:
        region (str): The region code to fetch upcoming movies for.
        language (str): The language code to fetch movies in.

    Returns:
        List[Movie]: A list of Movie objects.
    """
    tmdb_movies = fetch_upcoming_movies(region, language)

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

    db.session.commit()

    return movie_ids
