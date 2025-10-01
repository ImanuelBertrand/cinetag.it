from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.services.movie_service import get_lang_infos, get_region_infos


def test_get_region_infos(app, test_movies):
    """Test that get_region_infos returns the correct region information."""
    with app.app_context():
        # Get movie IDs from test_movies fixture
        movie_ids = [movie.id for movie in test_movies]

        # Test with US region (which is set in the test_movies fixture)
        region_infos = get_region_infos(movie_ids, "US")

        # Verify that we got region info for each movie
        assert len(region_infos) > 0
        assert all(movie_id in region_infos for movie_id in movie_ids)

        # Verify that all returned objects are MovieRegionInfo instances
        assert all(isinstance(info, MovieRegionInfo) for info in region_infos.values())

        # Verify that all returned objects have the correct region
        assert all(info.region == "US" for info in region_infos.values())


def test_get_lang_infos(app, test_movies):
    """Test that get_lang_infos returns the correct language information."""
    with app.app_context():
        # Get movie IDs from test_movies fixture
        movie_ids = [movie.id for movie in test_movies]

        # Test with English language (which is set in the test_movies fixture)
        lang_infos = get_lang_infos(movie_ids, "en")

        # Verify that we got language info for each movie
        assert len(lang_infos) > 0
        assert all(movie_id in lang_infos for movie_id in movie_ids)

        # Verify that all returned objects are MovieLanguageInfo instances
        assert all(isinstance(info, MovieLanguageInfo) for info in lang_infos.values())

        # Verify that all returned objects have the correct language
        assert all(info.language == "en" for info in lang_infos.values())


def test_get_region_infos_empty(app):
    """Test that get_region_infos handles empty input correctly."""
    with app.app_context():
        # Test with empty list of movie IDs
        region_infos = get_region_infos([], "US")

        # Should return an empty dictionary
        assert region_infos == {}


def test_get_lang_infos_empty(app):
    """Test that get_lang_infos handles empty input correctly."""
    with app.app_context():
        # Test with empty list of movie IDs
        lang_infos = get_lang_infos([], "en")

        # Should return an empty dictionary
        assert lang_infos == {}
