from unittest.mock import patch, MagicMock

from app.services.tmdb_service import (
    fetch_new_languages,
    update_regions,
    save_movie_list,
    sync_upcoming_movies,
    _sort_objects,
)


def test_fetch_new_languages(app):
    """Test that fetch_new_languages correctly processes languages from the API."""
    with app.app_context():
        # Mock the API response
        mock_languages = [
            {"iso_639_1": "en", "english_name": "English", "name": "English"},
            {"iso_639_1": "fr", "english_name": "French", "name": "Français"},
            {"iso_639_1": "es", "english_name": "Spanish", "name": "Español"},
        ]

        # Mock the database query result
        mock_db_languages = [
            MagicMock(code="en", english_name="English", name="English"),
            # fr is missing from DB to test creation
            # Add a language that's not in the API response to test deletion
            MagicMock(code="de", english_name="German", name="Deutsch"),
        ]

        # Set up the mocks
        with (
            patch("app.utils.tmdb.fetch_languages", return_value=mock_languages),
            patch("app.models.tmdb_language.TmdbLanguage.query") as mock_query,
            patch(
                "app.models.tmdb_language.TmdbLanguage.create_from_tmdb"
            ) as mock_create,
            patch("app.extensions.db.session.bulk_save_objects") as mock_bulk_save,
            patch("app.extensions.db.session.delete"),
            patch("app.extensions.db.session.add") as mock_add,
            patch("app.extensions.db.session.commit") as mock_commit,
        ):
            # Configure the mocks
            mock_query.all.return_value = mock_db_languages
            # Set update_from_tmdb to return False to avoid calling add
            mock_db_languages[0].update_from_tmdb.return_value = False
            mock_create.side_effect = lambda data: MagicMock(code=data["iso_639_1"])

            # Call the function
            fetch_new_languages()

            # Verify the function called the expected methods
            mock_query.all.assert_called_once()
            mock_create.assert_any_call(mock_languages[1])  # fr
            mock_create.assert_any_call(mock_languages[2])  # es
            mock_bulk_save.assert_called_once()
            # The add method is called for the German language that's being deleted
            mock_add.assert_called_once_with(mock_db_languages[1])
            mock_commit.assert_called_once()


def test_update_regions(app):
    """Test that update_regions correctly updates region information."""
    with app.app_context():
        # Mock the necessary functions
        with (
            patch("app.services.tmdb_service.fetch_new_regions") as mock_fetch,
            patch(
                "app.services.tmdb_service.calculate_region_sort_orders"
            ) as mock_calculate,
            patch("app.extensions.db.session.commit") as mock_commit,
        ):
            # Call the function
            update_regions()

            # Verify the function called the expected methods
            mock_fetch.assert_called_once()
            mock_calculate.assert_called_once()
            mock_commit.assert_called_once()


def test_save_movie_list(app):
    """Test that save_movie_list correctly processes a list of movies."""
    with app.app_context():
        # Create test data
        tmdb_movies = [
            {
                "id": 1,
                "original_title": "Test Movie 1",
                "popularity": 10.5,
                "original_language": "en",
                "release_date": "2023-01-01",
                "overview": "Test overview 1",
                "poster_path": "/path/to/poster1.jpg",
            },
            {
                "id": 2,
                "original_title": "Test Movie 2",
                "popularity": 8.3,
                "original_language": "fr",
                "release_date": "2023-02-01",
                "overview": "Test overview 2",
                "poster_path": "/path/to/poster2.jpg",
            },
        ]

        # Mock the database query results
        mock_existing_movie = MagicMock(id=1)
        mock_existing_movie.update_from_tmdb.return_value = True

        mock_existing_region_info = MagicMock(movie_id=1)
        mock_existing_region_info.update_from_tmdb.return_value = False

        mock_existing_lang_info = MagicMock(movie_id=1)
        mock_existing_lang_info.update_from_tmdb.return_value = True

        # Set up the mocks
        with (
            patch("app.models.movie.Movie.query") as mock_movie_query,
            patch("app.services.tmdb_service.get_lang_infos") as mock_get_lang_infos,
            patch(
                "app.services.tmdb_service.get_region_infos"
            ) as mock_get_region_infos,
            patch("app.models.movie.Movie.create_from_tmdb") as mock_create_movie,
            patch(
                "app.models.movie_region_info.MovieRegionInfo.create_from_tmdb"
            ) as mock_create_region,
            patch(
                "app.models.movie_language_info.MovieLanguageInfo.create_from_tmdb"
            ) as mock_create_lang,
            patch("app.extensions.db.session.bulk_save_objects") as mock_bulk_save,
            patch("app.extensions.db.session.add") as mock_add,
        ):
            # Configure the mocks
            mock_movie_query.filter.return_value.all.return_value = [
                mock_existing_movie
            ]
            mock_get_lang_infos.return_value = {1: mock_existing_lang_info}
            mock_get_region_infos.return_value = {1: mock_existing_region_info}

            mock_create_movie.return_value = MagicMock(id=2)
            mock_create_region.return_value = MagicMock(movie_id=2)
            mock_create_lang.return_value = MagicMock(movie_id=2)

            # Call the function
            save_movie_list(tmdb_movies, "US", "en")

            # Verify the function called the expected methods
            mock_movie_query.filter.assert_called_once()
            mock_get_lang_infos.assert_called_once_with([1, 2], "en")
            mock_get_region_infos.assert_called_once_with([1, 2], "US")

            # Movie 1 should be updated, Movie 2 should be created
            mock_add.assert_any_call(mock_existing_movie)
            mock_create_movie.assert_called_once_with(tmdb_movies[1])

            # Region info for Movie 2 should be created
            mock_create_region.assert_called_once()

            # Language info for Movie 2 should be created,
            # and for Movie 1 should be updated
            mock_add.assert_any_call(mock_existing_lang_info)
            mock_create_lang.assert_called_once()

            # Bulk save should be called 3 times (movies, region_infos, lang_infos)
            assert mock_bulk_save.call_count == 3


def test_sync_upcoming_movies(app):
    """Test that sync_upcoming_movies correctly syncs upcoming movies."""
    with app.app_context():
        # Mock the necessary functions
        with (
            patch("app.services.tmdb_service.fetch_upcoming_movies") as mock_fetch,
            patch("app.services.tmdb_service.save_movie_list") as mock_save,
            patch("app.models.misc_data.MiscData.save") as mock_misc_save,
            patch("app.extensions.db.session.commit") as mock_commit,
        ):
            # Configure the mocks
            mock_fetch.return_value = [
                {"id": 1, "original_title": "Movie 1"},
                {"id": 2, "original_title": "Movie 2"},
            ]

            # Call the function
            result = sync_upcoming_movies("US", "en")

            # Verify the function called the expected methods
            mock_fetch.assert_called_once_with("US", "en")
            mock_save.assert_called_once_with(mock_fetch.return_value, "US", "en")
            mock_misc_save.assert_called_once()
            mock_commit.assert_called_once()

            # Verify the result
            assert result == [1, 2]


def test_sort_objects(app):
    """Test that _sort_objects correctly sorts objects based on user counts."""
    with app.app_context():
        # Create test objects
        class TestObject:
            def __init__(self, code, name):
                self.code = code
                self.name = name
                self.sort_order = None

            def get_name(self):
                return self.name

        objects = [
            TestObject("en", "English"),
            TestObject("fr", "French"),
            TestObject("es", "Spanish"),
            TestObject("de", "German"),
            TestObject("it", "Italian"),
        ]

        # The average is 54, the median is 60
        # Only en and fr are above both average and median
        user_counts = {
            "en": 100,  # Popular (above average and median)
            "fr": 80,  # Popular (above average and median)
            "es": 60,  # Not popular (equal to median, not above)
            "de": 20,  # Not popular
            "it": 10,  # Not popular
        }

        # Configure the app config
        app.config["COUNT_TOP_SELECT_OPTION"] = 3

        # Mock the database session
        with patch("app.extensions.db.session.add") as mock_add:
            # Call the function
            _sort_objects(objects, user_counts)

            # Verify the sort orders
            # Top objects (en, fr) should have sort orders 10, 20
            # Other objects (es, de, it) should have sort orders 1010, 1020, 1030
            top_objects = [obj for obj in objects if obj.sort_order < 1000]
            other_objects = [obj for obj in objects if obj.sort_order >= 1000]

            assert len(top_objects) == 2
            assert len(other_objects) == 3

            # Verify that all objects were added to the session
            assert mock_add.call_count == 5
