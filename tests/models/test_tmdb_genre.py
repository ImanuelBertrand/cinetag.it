from app.extensions import db
from app.models.movie import Movie
from app.models.tmdb_genre import MovieGenre, TmdbGenre, TmdbGenreName


def test_tmdb_genre_repr(app) -> None:
    """Test TmdbGenre __repr__."""
    with app.app_context():
        genre = TmdbGenre(id=28)
        db.session.add(genre)
        db.session.commit()

        assert "28" in repr(genre)


def test_tmdb_genre_name_repr(app) -> None:
    """Test TmdbGenreName __repr__."""
    with app.app_context():
        genre = TmdbGenre(id=12)
        db.session.add(genre)
        db.session.commit()

        genre_name = TmdbGenreName(genre_id=12, language="en", name="Adventure")
        db.session.add(genre_name)
        db.session.commit()

        assert "12" in repr(genre_name)
        assert "en" in repr(genre_name)
        assert "Adventure" in repr(genre_name)


def test_movie_genre_repr(app) -> None:
    """Test MovieGenre __repr__."""
    with app.app_context():
        movie = Movie(
            id=700,
            original_title="Genre Test Movie",
            popularity=5.0,
            original_language="en",
        )
        db.session.add(movie)
        genre = TmdbGenre(id=99)
        db.session.add(genre)
        db.session.commit()

        movie_genre = MovieGenre(movie_id=700, genre_id=99)
        db.session.add(movie_genre)
        db.session.commit()

        assert "700" in repr(movie_genre)
        assert "99" in repr(movie_genre)
