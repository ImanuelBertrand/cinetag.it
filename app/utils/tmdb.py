from datetime import datetime, timedelta
from typing import List, Callable, Any

import requests
from flask import current_app

from app.exceptions import TMDbAPIError
from app.extensions import cache


def get_base_url() -> str:
    return "https://api.themoviedb.org/3"


def get_tmdb_url(path: str) -> str:
    return f"{get_base_url()}/{path.lstrip('/')}"


def get_tmdb_api_key() -> str:
    """
    Retrieve the TMDb API key from the application configuration.
    :return: The TMDb API key
    """
    return current_app.config.get("TMDB_API_KEY")


def _cached_tmdb_call(
    cache_key: str, fetch_function: Callable, ttl: int, *args, **kwargs
) -> Any:
    """
    Helper function to cache the results of a TMDb API call.
    :param cache_key:
    :param fetch_function:
    :param args:
    :param kwargs:
    :return: The cached data or the fetched data
    """
    data = cache.get(cache_key)

    if not data:
        data = fetch_function(*args, **kwargs)
        cache.set(cache_key, data, timeout=ttl)

    return data


def uncached_fetch_upcoming_movies(region: str, language: str) -> List[dict]:
    api_key = get_tmdb_api_key()
    if not api_key:
        raise TMDbAPIError("TMDb API key is not configured.")

    now = datetime.now()
    params = {
        "api_key": api_key,
        "region": region,
        "language": language,
        "release_date.gte": now.strftime("%Y-%m-%d"),
        "release_date.lte": (now + timedelta(days=30)).strftime("%Y-%m-%d"),
    }

    url = get_tmdb_url("discover/movie")
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise TMDbAPIError(
            f"TMDb API request failed with status code {response.status_code}",
            status_code=response.status_code,
        )

    return response.json().get("results", [])


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
        uncached_fetch_upcoming_movies,
        3600,
        region,
        language,
    )
