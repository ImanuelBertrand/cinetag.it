from datetime import datetime, timedelta

import requests
from flask import current_app

from app.exceptions import TMDbAPIError
from app.extensions import cache


def get_base_url():
    """
    Retrieve the base URL for the TMDb API.

    Returns:
        str: The base URL for the TMDb API.
    """
    return "https://api.themoviedb.org/3"


def get_tmdb_api_key() -> str:
    """
    Retrieve the TMDb API key from the application configuration.

    Returns:
        str: The TMDb API key.
    """
    return current_app.config.get("TMDB_API_KEY")


def _cached_tmdb_call(cache_key, fetch_function, ttl, *args, **kwargs):
    """
    Helper function to cache the results of a TMDb API call.
    :param cache_key:
    :param fetch_function:
    :param args:
    :param kwargs:
    :return:
    """
    data = cache.get(cache_key)

    if not data:
        data = fetch_function(*args, **kwargs)
        cache.set(cache_key, data, timeout=ttl)

    return data


def uncached_fetch_upcoming_movies(region="US", language="en-US"):
    api_key = get_tmdb_api_key()
    if not api_key:
        raise TMDbAPIError("TMDb API key is not configured.")

    base_url = get_base_url()
    now = datetime.now()
    params = {
        "api_key": api_key,
        "region": region,
        "language": language,
        "release_date.gte": now.strftime("%Y-%m-%d"),
        "release_date.lte": (now + timedelta(days=30)).strftime("%Y-%m-%d"),
    }

    url = f"{base_url}/discover/movie"
    response = requests.get(url, params=params)
    if response.status_code != 200:
        raise TMDbAPIError(
            f"TMDb API request failed with status code {response.status_code}",
            status_code=response.status_code,
        )

    return response.json().get("results", [])


def fetch_upcoming_movies(region="US", language="en-US"):
    """
    Fetch a list of upcoming movies from TMDb for a specific region using the discover endpoint.

    Args:
        region (str): The region code to fetch upcoming movies for (default is 'US').
        language (str): The language code to fetch movies in (default is 'en-US').

    Returns:
        list: A list of dictionaries, each containing details of an upcoming movie.
    """
    return _cached_tmdb_call(
        f"upcoming_movies_{region}_{language}",
        uncached_fetch_upcoming_movies,
        3600,
        region,
        language,
    )
