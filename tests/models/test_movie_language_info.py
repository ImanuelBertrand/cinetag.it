from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo


def _create_movie(app, movie_id: int) -> None:
    """Helper to create a base movie."""
    with app.app_context():
        movie = Movie(
            id=movie_id,
            original_title="Base Movie",
            popularity=5.0,
            original_language="en",
        )
        db.session.add(movie)
        db.session.commit()


def test_create_from_tmdb_with_language(app) -> None:
    """Test MovieLanguageInfo.create_from_tmdb with explicit language."""
    with app.app_context():
        _create_movie(app, 300)

        data = {
            "title": "French Title",
            "overview": "French overview",
            "tagline": "A tagline",
            "runtime": 110,
        }

        lang_info = MovieLanguageInfo.create_from_tmdb(300, data, language="fr")

        assert lang_info.movie_id == 300
        assert lang_info.language == "fr"
        assert lang_info.title == "French Title"
        assert lang_info.overview == "French overview"
        assert lang_info.tagline == "A tagline"
        assert lang_info.runtime == 110


def test_create_from_tmdb_without_language(app) -> None:
    """Test MovieLanguageInfo.create_from_tmdb with data containing iso_639_1."""
    with app.app_context():
        _create_movie(app, 301)

        data = {
            "iso_639_1": "de",
            "data": {
                "title": "German Title",
                "overview": "German overview",
                "tagline": "Tagline",
                "runtime": 95,
            },
        }

        lang_info = MovieLanguageInfo.create_from_tmdb(301, data)

        assert lang_info.movie_id == 301
        assert lang_info.language == "de"
        assert lang_info.title == "German Title"


def test_update_from_tmdb_no_changes(app) -> None:
    """Test MovieLanguageInfo.update_from_tmdb returns False when nothing changes."""
    with app.app_context():
        _create_movie(app, 302)

        lang_info = MovieLanguageInfo(
            movie_id=302,
            language="en",
            title="Same Title",
            overview="Same overview",
            poster_path="/same/path.jpg",
            tagline="Same tagline",
            runtime=100,
        )
        db.session.add(lang_info)
        db.session.commit()

        data = {
            "title": "Same Title",
            "overview": "Same overview",
            "poster_path": "/same/path.jpg",
            "tagline": "Same tagline",
            "runtime": 100,
        }

        updated = lang_info.update_from_tmdb(data)
        assert updated is False


def test_update_from_tmdb_with_changes(app) -> None:
    """Test MovieLanguageInfo.update_from_tmdb returns True and updates."""
    with app.app_context():
        _create_movie(app, 303)

        lang_info = MovieLanguageInfo(
            movie_id=303,
            language="en",
            title="Old Title",
            overview="Old overview",
            poster_path="/old/path.jpg",
            tagline="Old tagline",
            runtime=90,
        )
        db.session.add(lang_info)
        db.session.commit()

        data = {
            "title": "New Title",
            "overview": "New overview",
            "poster_path": "/new/path.jpg",
            "tagline": "New tagline",
            "runtime": 120,
        }

        updated = lang_info.update_from_tmdb(data)
        assert updated is True
        assert lang_info.title == "New Title"
        assert lang_info.overview == "New overview"
        assert lang_info.poster_path == "/new/path.jpg"
        assert lang_info.tagline == "New tagline"
        assert lang_info.runtime == 120


def test_update_from_tmdb_runtime_none(app) -> None:
    """Test that updating runtime to None/0 sets it to None."""
    with app.app_context():
        _create_movie(app, 304)

        lang_info = MovieLanguageInfo(
            movie_id=304,
            language="en",
            title="Title",
            overview="Overview",
            runtime=100,
        )
        db.session.add(lang_info)
        db.session.commit()

        data = {
            "title": "Title",
            "overview": "Overview",
            "runtime": 0,
        }

        updated = lang_info.update_from_tmdb(data)
        assert updated is True
        assert lang_info.runtime is None


def test_repr(app) -> None:
    """Test MovieLanguageInfo __repr__."""
    with app.app_context():
        _create_movie(app, 305)

        lang_info = MovieLanguageInfo(
            movie_id=305,
            language="en",
            title="Title",
        )
        db.session.add(lang_info)
        db.session.commit()

        assert "305" in repr(lang_info)
        assert "en" in repr(lang_info)
