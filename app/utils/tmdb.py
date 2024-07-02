import logging
from datetime import datetime, timedelta
from typing import List, Callable, Any

import requests
from flask import current_app

from app.exceptions import TMDbAPIError
from app.extensions import cache

_logger = logging.getLogger(__name__)


def get_base_url() -> str:
    return "https://api.themoviedb.org/3"


def get_tmdb_url(path: str) -> str:
    return f"{get_base_url()}/{path.lstrip('/')}"


def get_tmdb_api_key() -> str:
    """
    Retrieve the TMDb API key from the application configuration.
    :return: The TMDb API key
    """
    key = current_app.config.get("TMDB_API_KEY")
    if not key:
        raise TMDbAPIError("TMDb API key is not configured.")
    return key


def _cached_tmdb_call(
    cache_key: str, ttl: int, fetch_function: Callable, *args, **kwargs
) -> Any:
    """
    Helper function to cache the results of a TMDb API call.
    :param cache_key: The cache key to use
    :param fetch_function: The (uncached) function to fetch the data
    :param args: The arguments to pass to the fetch function
    :param kwargs: The keyword arguments to pass to the fetch function
    :return: The cached data or the fetched data
    """
    data = cache.get(cache_key)

    if not data:
        _logger.debug("Cache miss for key %s", cache_key)
        data = fetch_function(*args, **kwargs)
        cache.set(cache_key, data, timeout=ttl)

    return data


def uncached_fetch_upcoming_movies(region: str, language: str) -> List[dict]:
    api_key = get_tmdb_api_key()

    now = datetime.now()
    cutoff_date = now + timedelta(days=90)
    params = {
        "api_key": api_key,
        "region": region,
        "language": language,
        "release_date.gte": now.strftime("%Y-%m-%d"),
        "release_date.lte": cutoff_date.strftime("%Y-%m-%d"),
        "with_release_type": "3",  # Theatrical
        "page": 1,
    }

    url = get_tmdb_url("discover/movie")
    all_movies = {}
    while True:
        response = requests.get(url, params=params)
        _logger.debug(
            "Response %s for GET %s with: %s", response.status_code, url, params
        )
        if response.status_code != 200:
            raise TMDbAPIError(
                f"TMDb API request failed with status code {response.status_code}",
                status_code=response.status_code,
            )
        data = response.json()
        for movie in data["results"]:
            all_movies[movie["id"]] = movie
        if data["page"] >= data["total_pages"]:
            break
        params["page"] += 1

    return list(all_movies.values())


def fetch_upcoming_movies(region: str, language: str) -> List[dict]:
    """
    Fetch a list of upcoming movies from TMDb for a specific region
    using the discover endpoint.

    :param region: The region code to fetch upcoming movies for.
    :param language: The language code to fetch movies in.
    :return: A list of upcoming movies
    """
    return _cached_tmdb_call(
        f"upcoming_movies_{region}_{language}",
        3600,
        uncached_fetch_upcoming_movies,
        region,
        language,
    )


def uncached_fetch_movie_details(movie_id: int, language: str) -> dict:
    api_key = get_tmdb_api_key()

    url = get_tmdb_url(f"movie/{movie_id}")
    params = {"api_key": api_key, "language": language}
    response = requests.get(url, params=params)
    _logger.debug("Response %s for GET %s", response.status_code, url)
    if response.status_code != 200:
        raise TMDbAPIError(
            f"TMDb API request failed with status code {response.status_code}",
            status_code=response.status_code,
        )
    return response.json()


def fetch_movie_details(movie_id: int, language: str) -> dict:
    return _cached_tmdb_call(
        f"movie_{movie_id}_{language}",
        86400,
        uncached_fetch_movie_details,
        movie_id,
        language,
    )
