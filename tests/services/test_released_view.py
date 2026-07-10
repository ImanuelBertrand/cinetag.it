from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.user_movie import UserMovie
from app.services.user_service import get_movies_based_on_filter


def _make_movie(movie_id, days_from_today, decision=None, user=None, popularity=0.0):
    """Create a movie releasing `days_from_today` days from today (negative =
    already released) and optionally tag it for `user`."""
    release_date = datetime.now(UTC).date() + timedelta(days=days_from_today)
    title = f"Movie {movie_id}"
    db.session.add(
        Movie(
            id=movie_id,
            original_title=title,
            popularity=popularity,
            original_language="en",
            imdb_id=f"tt{movie_id:07d}",
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
            overview=f"Overview {movie_id}",
            poster_path=f"/poster/{movie_id}.jpg",
        )
    )
    if decision and user:
        db.session.add(UserMovie(user_id=user.id, movie_id=movie_id, decision=decision))


def test_released_returns_only_past_tagged_desc(app, test_user) -> None:
    """Released mode returns approve+maybe past movies, newest first."""
    with app.app_context():
        _make_movie(1, -1, "approve", test_user)  # newest release
        _make_movie(2, -5, "maybe", test_user)  # oldest release
        _make_movie(3, -3, "disapprove", test_user)  # excluded: disapprove
        _make_movie(4, -3, None)  # excluded: untagged
        _make_movie(5, 3, "approve", test_user)  # excluded: still upcoming
        db.session.commit()

        result = get_movies_based_on_filter(user=test_user, mode="released", limit=10)

        ids = [m["id"] for m in result["movies"]]
        # Only past approve/maybe, ordered by release date descending
        assert ids == [1, 2]
        assert all(m["decision"] in ("approve", "maybe") for m in result["movies"])


def test_released_includes_release_day(app, test_user) -> None:
    """A movie released today counts as released — the view must agree with
    the dashboard's 'Out now' section, which includes release day."""
    with app.app_context():
        _make_movie(1, 0, "approve", test_user)  # out today
        _make_movie(2, -2, "approve", test_user)  # released two days ago
        _make_movie(3, 1, "approve", test_user)  # tomorrow: still upcoming
        db.session.commit()

        result = get_movies_based_on_filter(user=test_user, mode="released", limit=10)

        assert [m["id"] for m in result["movies"]] == [1, 2]


def test_released_descending_cursor_pagination(app, test_user) -> None:
    """The descending cursor paginates without skips or repeats."""
    with app.app_context():
        # Six past approved movies, releasing 1..6 days ago
        for i in range(6):
            _make_movie(i + 1, -(i + 1), "approve", test_user)
        db.session.commit()

        first = get_movies_based_on_filter(user=test_user, mode="released", limit=3)
        assert [m["id"] for m in first["movies"]] == [1, 2, 3]
        assert first["has_more"] is True

        second = get_movies_based_on_filter(
            user=test_user,
            mode="released",
            min_release_date=datetime.fromisoformat(first["next_release_date"]).date(),
            min_movie_id=first["next_movie_id"],
            limit=3,
        )
        assert [m["id"] for m in second["movies"]] == [4, 5, 6]
        assert second["has_more"] is False


def test_released_route_renders(client, app, test_user) -> None:
    """The /movies/released page renders with its title and active chip."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        token = create_access_token(identity=str(test_user.id))
    client.set_cookie("access_token_cookie", token)

    response = client.get("/movies/released")
    assert response.status_code == 200
    assert b"Recently released" in response.data
    assert b'data-filter-mode="released"' in response.data


def test_released_api_returns_past_movies(client, app, test_user) -> None:
    """The movies API serves the released pool with imdb+poster requirements."""
    from flask_jwt_extended import create_access_token

    with app.app_context():
        _make_movie(1, -2, "approve", test_user)
        _make_movie(2, -4, "maybe", test_user)
        _make_movie(3, 5, "approve", test_user)  # upcoming, excluded
        db.session.commit()
        token = create_access_token(identity=str(test_user.id))
    client.set_cookie("access_token_cookie", token)

    response = client.get("/api/movies/released")
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert [m["id"] for m in data["movies"]] == [1, 2]
