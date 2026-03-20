from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo


def test_movie_create_from_tmdb(app) -> None:
    """Test Movie.create_from_tmdb creates a Movie from TMDB data."""
    with app.app_context():
        data = {
            "id": 999,
            "original_title": "Test Movie",
            "popularity": 10.5,
            "original_language": "en",
            "runtime": 120,
            "imdb_id": "tt1234567",
            "origin_country": ["US", "GB"],
            "spoken_languages": [
                {"iso_639_1": "en"},
                {"iso_639_1": "fr"},
            ],
        }

        movie = Movie.create_from_tmdb(data)

        assert movie.id == 999
        assert movie.original_title == "Test Movie"
        assert movie.popularity == 10.5
        assert movie.original_language == "en"
        assert movie.runtime == 120
        assert movie.imdb_id == "tt1234567"
        assert movie.origin_country == "US,GB"
        assert movie.spoken_languages == "en,fr"


def test_movie_create_from_tmdb_minimal(app) -> None:
    """Test Movie.create_from_tmdb with minimal data."""
    with app.app_context():
        data = {
            "id": 888,
            "original_title": "Minimal Movie",
            "popularity": 5.0,
            "original_language": "fr",
        }

        movie = Movie.create_from_tmdb(data)

        assert movie.id == 888
        assert movie.original_title == "Minimal Movie"
        assert movie.runtime is None
        assert movie.imdb_id is None
        assert movie.origin_country == ""
        assert movie.spoken_languages == ""


def test_movie_update_from_tmdb_no_changes(app) -> None:
    """Test Movie.update_from_tmdb returns False when nothing changes."""
    with app.app_context():
        movie = Movie(
            id=101,
            original_title="Same Title",
            popularity=10.0,
            original_language="en",
        )
        db.session.add(movie)
        db.session.commit()

        data = {
            "original_title": "Same Title",
            "popularity": 10.0,
            "original_language": "en",
        }

        updated = movie.update_from_tmdb(data)
        assert updated is False


def test_movie_update_from_tmdb_with_changes(app) -> None:
    """Test Movie.update_from_tmdb returns True and updates when data changes."""
    with app.app_context():
        movie = Movie(
            id=102,
            original_title="Old Title",
            popularity=5.0,
            original_language="en",
        )
        db.session.add(movie)
        db.session.commit()

        data = {
            "original_title": "New Title",
            "popularity": 8.0,
            "original_language": "fr",
            "runtime": 90,
            "imdb_id": "tt9999999",
            "origin_country": ["FR"],
            "spoken_languages": [{"iso_639_1": "fr"}],
        }

        updated = movie.update_from_tmdb(data)
        assert updated is True
        assert movie.original_title == "New Title"
        assert movie.popularity == 8.0
        assert movie.original_language == "fr"
        assert movie.runtime == 90
        assert movie.imdb_id == "tt9999999"
        assert movie.origin_country == "FR"
        assert movie.spoken_languages == "fr"


def test_movie_get_localized_data_with_language_infos(app) -> None:
    """Test Movie.get_localized_data with pre-loaded language infos dict."""
    with app.app_context():
        movie = Movie(
            id=103,
            original_title="Original Title",
            popularity=5.0,
            original_language="fr",
        )
        db.session.add(movie)
        db.session.commit()

        lang_info_en = MovieLanguageInfo(
            movie_id=103,
            language="en",
            title="English Title",
            overview="English overview",
            poster_path="/path/poster.jpg",
        )
        db.session.add(lang_info_en)
        db.session.commit()

        language_infos = {"en": lang_info_en}
        result = movie.get_localized_data("en", language_infos)

        assert result["title"] == "English Title"
        assert result["overview"] == "English overview"
        assert result["poster_path"] == "/path/poster.jpg"


def test_movie_get_localized_data_fallback_to_original(app) -> None:
    """Test Movie.get_localized_data falls back to original_title when no lang info."""
    with app.app_context():
        movie = Movie(
            id=104,
            original_title="Fallback Title",
            popularity=5.0,
            original_language="ja",
        )
        db.session.add(movie)
        db.session.commit()

        result = movie.get_localized_data("de", {})

        assert result["title"] == "Fallback Title"


def test_movie_get_localized_data_without_language_infos_dict(app) -> None:
    """Test Movie.get_localized_data loads from relationships when no dict provided."""
    with app.app_context():
        movie = Movie(
            id=105,
            original_title="Direct Title",
            popularity=5.0,
            original_language="en",
        )
        db.session.add(movie)

        lang_info = MovieLanguageInfo(
            movie_id=105,
            language="en",
            title="Direct English Title",
            overview="Direct overview",
        )
        db.session.add(lang_info)
        db.session.commit()

        # Refresh to load relationships
        db.session.expire_all()
        movie = db.session.get(Movie, 105)
        assert movie is not None

        result = movie.get_localized_data("en")

        assert result["title"] == "Direct English Title"


def test_movie_repr(app) -> None:
    """Test Movie __repr__."""
    with app.app_context():
        movie = Movie(
            id=200,
            original_title="Repr Movie",
            popularity=1.0,
            original_language="en",
        )
        db.session.add(movie)
        db.session.commit()
        assert "200" in repr(movie)
        assert "Repr Movie" in repr(movie)
