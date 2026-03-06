from datetime import UTC, date, datetime
from unittest.mock import MagicMock, patch

import pytest

from app.errors import TMDbAPIError
from app.utils.tmdb import (
    fetch_genre_list,
    fetch_upcoming_movies,
    get_base_url,
    get_tmdb_api_token,
    get_tmdb_url,
)


def test_get_base_url(app) -> None:
    """Test get_base_url returns the correct base URL."""
    with app.app_context():
        url = get_base_url()
        assert url == "https://api.themoviedb.org/3"


def test_get_tmdb_url(app) -> None:
    """Test get_tmdb_url constructs the correct URL."""
    with app.app_context():
        url = get_tmdb_url("movie/123")
        assert url == "https://api.themoviedb.org/3/movie/123"

        # Test with leading slash
        url = get_tmdb_url("/movie/123")
        assert url == "https://api.themoviedb.org/3/movie/123"


def test_get_tmdb_api_token_from_env(app) -> None:
    """Test get_tmdb_api_token retrieves token from environment variable."""
    with app.app_context():
        with patch.dict("os.environ", {"TMDB_API_KEY": "env-test-token"}):
            token = get_tmdb_api_token()
            assert token == "env-test-token"


def test_get_tmdb_api_token_from_config(app) -> None:
    """Test get_tmdb_api_token retrieves token from Flask config."""
    with app.app_context():
        app.config["TMDB_API_KEY"] = "config-test-token"
        with patch.dict("os.environ", {}, clear=False):
            # Remove TMDB_API_KEY from environment if set
            import os

            env_token = os.environ.pop("TMDB_API_KEY", None)
            try:
                token = get_tmdb_api_token()
                assert token == "config-test-token"
            finally:
                if env_token:
                    os.environ["TMDB_API_KEY"] = env_token


def test_get_tmdb_api_token_missing(app) -> None:
    """Test get_tmdb_api_token raises TMDbAPIError when not configured."""
    with app.app_context():
        app.config["TMDB_API_KEY"] = None
        import os

        env_token = os.environ.pop("TMDB_API_KEY", None)
        try:
            with pytest.raises(TMDbAPIError, match="not configured"):
                get_tmdb_api_token()
        finally:
            if env_token:
                os.environ["TMDB_API_KEY"] = env_token


def test_fetch_upcoming_movies_from_cache(app) -> None:
    """Test fetch_upcoming_movies returns cached results when available."""
    with app.app_context():
        cached_movies = [{"id": 1, "original_title": "Cached Movie"}]

        with patch("app.utils.tmdb.cache") as mock_cache:
            mock_cache.get.return_value = cached_movies

            result = fetch_upcoming_movies("US", "en")

        assert result == cached_movies
        mock_cache.get.assert_called_once_with("upcoming_movies_US_en")


def test_fetch_upcoming_movies_cache_miss(app) -> None:
    """Test fetch_upcoming_movies fetches from API when cache misses."""
    with app.app_context():
        api_movies = [
            {"id": 1, "original_title": "New Movie", "release_date": "2025-06-01"}
        ]
        api_response = {"results": api_movies, "page": 1, "total_pages": 1}

        with (
            patch("app.utils.tmdb.cache") as mock_cache,
            patch("app.utils.tmdb._get_json", return_value=api_response),
        ):
            mock_cache.get.return_value = None

            result = fetch_upcoming_movies("US", "en")

        assert len(result) == 1
        assert result[0]["id"] == 1


def test_fetch_genre_list(app) -> None:
    """Test fetch_genre_list returns genres from the API."""
    with app.app_context():
        genres_response = {"genres": [{"id": 28, "name": "Action"}]}

        with patch("app.utils.tmdb.cache") as mock_cache:
            mock_cache.get.return_value = genres_response

            result = fetch_genre_list("en")

        assert len(result) == 1
        assert result[0]["id"] == 28
        assert result[0]["name"] == "Action"


def test_get_raises_tmdb_api_error_on_non_200(app) -> None:
    """Test _get raises TMDbAPIError when API returns non-200 status."""
    from app.utils.tmdb import _get

    with app.app_context():
        app.config["TMDB_API_KEY"] = "test-key"

        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.text = "Not found"

        with (
            patch("requests.get", return_value=mock_response),
            patch.dict("os.environ", {"TMDB_API_KEY": "test-key"}),
        ):
            with pytest.raises(TMDbAPIError):
                _get("movie/99999")


def test_fetch_changed_movies_converts_dates(app) -> None:
    """Test fetch_changed_movies handles datetime/date objects correctly."""
    from app.utils.tmdb import fetch_changed_movies

    with app.app_context():
        start = date(2025, 1, 1)
        end = datetime(2025, 1, 31, tzinfo=UTC)

        with patch("app.utils.tmdb.cache") as mock_cache:
            mock_cache.get.return_value = [1, 2, 3]

            result = fetch_changed_movies(start, end)

        assert result == [1, 2, 3]
        mock_cache.get.assert_called_once_with("changes_movies_2025-01-01_2025-01-31")
