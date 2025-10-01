import logging
import os
from collections.abc import Callable
from datetime import date, datetime
from typing import Any

import requests
from flask import current_app

from app.exceptions import TMDbAPIError
from app.extensions import cache

_logger = logging.getLogger(__name__)

DEFAULT_TTL = 72000  # 20 hours to allow for irregularities in daily cron jobs


def get_base_url() -> str:
    return "https://api.themoviedb.org/3"


def get_tmdb_api_token() -> str:
    """
    Retrieve the TMDb API token from environment variables
    or application configuration.
    :return: The TMDb API token
    """
    # First check environment variable
    token = os.environ.get("TMDB_API_TOKEN")

    # Fall back to configuration file if not in environment
    if not token:
        token = current_app.config.get("TMDB_API_TOKEN")

    if not token:
        raise TMDbAPIError("TMDb API Token is not configured.")
    return token


def get_tmdb_url(path: str) -> str:
    return f"{get_base_url()}/{path.lstrip('/')}"


def _get(
    url: str,
    params: dict[str, str] | None = None,
    headers: dict[str, str] | None = None,
):
    if not params:
        params = {}
    if not headers:
        headers = {}

    headers["Authorization"] = f"Bearer {get_tmdb_api_token()}"

    response = requests.get(
        get_tmdb_url(url), params=params, headers=headers, timeout=5
    )
    _logger.debug("Response %s for GET %s", response.status_code, url)

    if response.status_code != 200:
        _logger.error(
            "TMDb API request failed with status code %s", response.status_code
        )

        debug_headers = headers
        if "Authorization" in debug_headers:
            debug_headers["Authorization"] = "[REDACTED]"

        _logger.error(
            "Request was: GET %s with params %s and headers %s",
            url,
            params,
            headers,
        )
        _logger.error("Response: %s", response.text)
        raise TMDbAPIError(
            f"TMDb API request failed with status code {response.status_code}",
            status_code=response.status_code,
        )

    return response


def _get_json(url: str, params: dict[str, str] | None = None):
    return _get(url, params=params).json()


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


def uncached_fetch_upcoming_movies(region: str, language: str) -> list[dict]:
    params = {
        "region": region,
        "language": language,
        "release_date.gte": datetime.now().strftime("%Y-%m-%d"),
        "with_release_type": "3",  # Theatrical
        "page": 1,
    }

    all_movies = {}
    while True:
        data = _get_json("discover/movie", params=params)
        for movie in data["results"]:
            all_movies[movie["id"]] = movie
        if data["page"] >= data["total_pages"]:
            break
        params["page"] += 1

    return list(all_movies.values())


def uncached_fetch_movie_changes(start_date: str, end_date: str) -> list[int]:
    params = {
        "start_date": start_date,
        "end_date": end_date,
        "page": 1,
    }

    all_movies = set()
    while True:
        data = _get_json("movie/changes", params=params)
        for item in data["results"]:
            all_movies.add(item["id"])
        if data["page"] >= data["total_pages"]:
            break
        params["page"] += 1
        if params["page"] >= 500:
            _logger.warning("Total pages exceeds 500, truncating")
            break

    return list(all_movies)


def fetch_upcoming_movies(region: str, language: str) -> list[dict]:
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


def fetch_movie_details(movie_id: int, language: str) -> dict:
    return _cached_tmdb_call(
        f"movie_{movie_id}_{language}",
        DEFAULT_TTL,
        _get_json,
        f"movie/{movie_id}",
        params={"language": language},
    )


def fetch_languages() -> list[dict]:
    return _cached_tmdb_call(
        "languages",
        DEFAULT_TTL,
        _get_json,
        "configuration/languages",
    )


def fetch_regions() -> list[dict]:
    return _cached_tmdb_call(
        "regions",
        DEFAULT_TTL,
        _get_json,
        "configuration/countries",
    )


def fetch_movie_languages(movie_id: int) -> list[dict]:
    return _cached_tmdb_call(
        f"movie_languages_{movie_id}",
        DEFAULT_TTL,
        _get_json,
        f"movie/{movie_id}/translations",
    )["translations"]


def fetch_movie_images(movie_id: int) -> dict[str, Any]:
    return _cached_tmdb_call(
        f"movie_images_{movie_id}",
        DEFAULT_TTL,
        _get_json,
        f"movie/{movie_id}/images",
    )


def fetch_release_dates(movie_id: int) -> list[dict[str, Any]]:
    return _cached_tmdb_call(
        f"movie_release_dates_{movie_id}",
        DEFAULT_TTL,
        _get_json,
        f"movie/{movie_id}/release_dates",
    )["results"]


def fetch_changed_movies(
    start_date: datetime | date | str, end_date: datetime | date | str
) -> list[dict[str, Any]]:
    if isinstance(start_date, (datetime, date)):
        start_date = start_date.strftime("%Y-%m-%d")
    if isinstance(end_date, (datetime, date)):
        end_date = end_date.strftime("%Y-%m-%d")
    return _cached_tmdb_call(
        f"changes_movies_{start_date}_{end_date}",
        3600,
        uncached_fetch_movie_changes,
        start_date,
        end_date,
    )
