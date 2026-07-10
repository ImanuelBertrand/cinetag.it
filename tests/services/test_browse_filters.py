"""Phase 4: genre filtering and popularity sort/cursor."""

from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.tmdb_genre import MovieGenre, TmdbGenre
from app.services.user_service import get_available_genres, get_movies_based_on_filter


def _ensure_genres(genre_ids):
    """Create the parent TmdbGenre rows and flush them, so the MovieGenre FK
    is satisfied (there is no ORM relationship to order the inserts)."""
    with db.session.no_autoflush:
        for gid in genre_ids:
            if db.session.get(TmdbGenre, gid) is None:
                db.session.add(TmdbGenre(id=gid))
    db.session.flush()


def _make_movie(movie_id, popularity=1.0, genres=None, title=None):
    genres = genres or []
    _ensure_genres(genres)
    release_date = datetime.now(UTC).date() + timedelta(days=5)
    title = title or f"Movie {movie_id}"
    db.session.add(
        Movie(
            id=movie_id,
            original_title=title,
            popularity=popularity,
            original_language="en",
        )
    )
    db.session.add(
        MovieRegionInfo(movie_id=movie_id, region="US", release_date=release_date)
    )
    db.session.add(
        MovieLanguageInfo(
            movie_id=movie_id,
            language="en",
            title=title,
            overview="o",
            poster_path=f"/p/{movie_id}.jpg",
        )
    )
    for gid in genres:
        db.session.add(MovieGenre(movie_id=movie_id, genre_id=gid))


def test_genre_filter_no_duplicate_rows(app, test_user) -> None:
    """Multi-genre filters use OR semantics and never duplicate a movie."""
    with app.app_context():
        _make_movie(1, genres=[28, 12])  # action + adventure
        _make_movie(2, genres=[28])  # action
        _make_movie(3, genres=[35])  # comedy
        db.session.commit()

        result = get_movies_based_on_filter(
            user=test_user, mode="all", genre_ids=[28, 12], limit=10
        )
        ids = [m["id"] for m in result["movies"]]
        # Movie 1 matches both genres but must appear exactly once
        assert sorted(ids) == [1, 2]
        assert len(ids) == len(set(ids))


def test_popularity_cursor_handles_ties(app, test_user) -> None:
    """Popularity pagination covers every movie once across equal-pop ties."""
    with app.app_context():
        _make_movie(1, popularity=10.0)
        _make_movie(2, popularity=10.0)
        _make_movie(3, popularity=5.0)
        _make_movie(4, popularity=5.0)
        _make_movie(5, popularity=5.0)
        db.session.commit()

        seen = []
        cursor_pop = None
        cursor_id = None
        for _ in range(5):  # safety bound
            page = get_movies_based_on_filter(
                user=test_user,
                mode="all",
                sort="popularity",
                min_popularity=cursor_pop,
                min_movie_id=cursor_id,
                limit=2,
            )
            seen.extend(m["id"] for m in page["movies"])
            if not page["has_more"]:
                break
            cursor_pop = page["next_popularity"]
            cursor_id = page["next_movie_id"]

        # Every movie exactly once, ranked popularity desc then id desc
        assert seen == [2, 1, 5, 4, 3]


def test_name_and_genre_filters_compose(app, test_user) -> None:
    """Name and genre filters intersect."""
    with app.app_context():
        _make_movie(1, genres=[28], title="Star Action")
        _make_movie(2, genres=[28], title="Regular Action")
        _make_movie(3, genres=[35], title="Star Comedy")
        db.session.commit()

        result = get_movies_based_on_filter(
            user=test_user,
            mode="all",
            name_filter="Star",
            genre_ids=[28],
            limit=10,
        )
        assert [m["id"] for m in result["movies"]] == [1]


def test_get_available_genres_localized(app) -> None:
    """Available genres list only genres present on movies, localized."""
    from app.models.tmdb_genre import TmdbGenreName

    with app.app_context():
        _make_movie(1, genres=[28])
        _ensure_genres([99])  # a genre with no movie attached
        db.session.add(TmdbGenreName(genre_id=28, language="en", name="Action"))
        db.session.add(TmdbGenreName(genre_id=99, language="en", name="Nope"))
        db.session.commit()

        genres = get_available_genres("en")
        ids = {g["id"] for g in genres}
        assert 28 in ids
        assert 99 not in ids  # not attached to any movie
        assert next(g["name"] for g in genres if g["id"] == 28) == "Action"
