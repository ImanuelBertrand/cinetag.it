from datetime import datetime

from app.extensions import db
from app.services.user_service import (
    get_movies_based_on_filter,
    get_pending_count,
    user_has_any_tags,
)


def test_name_filter_with_pagination(app, test_user, test_movies) -> None:
    """Test that display_name filter works correctly with pagination."""
    with app.app_context():
        # Test case 1: First page with display_name filter
        result = get_movies_based_on_filter(
            user=test_user,
            mode="all",
            name_filter="Star",
            limit=2,  # Small limit to test pagination
        )

        # Should find movies with "Star" in the title
        assert len(result["movies"]) > 0
        assert all("Star" in movie["title"] for movie in result["movies"])
        assert result["has_more"] is True  # Should have more pages

        # Test case 2: Pagination with display_name filter
        # Get next page using pagination parameters from first result
        next_result = get_movies_based_on_filter(
            user=test_user,
            mode="all",
            name_filter="Star",
            min_release_date=datetime.fromisoformat(result["next_release_date"]).date(),
            min_movie_id=result["next_movie_id"],
            limit=2,
        )

        # Should find more movies with "Star" in the title
        assert len(next_result["movies"]) > 0
        assert all("Star" in movie["title"] for movie in next_result["movies"])

        # Test case 3: No matching movies
        no_match_result = get_movies_based_on_filter(
            user=test_user, mode="all", name_filter="NonExistentTitle", limit=10
        )

        # Should return empty list
        assert len(no_match_result["movies"]) == 0
        assert no_match_result["has_more"] is False


def test_name_filter_with_other_filters(app, test_user, test_movies) -> None:
    """Test that display_name filter works correctly with other filters."""
    with app.app_context():
        # Test with mode filter
        approved_result = get_movies_based_on_filter(
            user=test_user, mode="approved", name_filter="Star", limit=10
        )

        assert len(approved_result["movies"]) > 0
        # Should only include approved movies with "Star" in the title
        assert all("Star" in movie["title"] for movie in approved_result["movies"])
        assert all(
            movie["decision"] == "approve" for movie in approved_result["movies"]
        )

        # Test with poster filter
        poster_result = get_movies_based_on_filter(
            user=test_user, mode="all", need_poster=True, name_filter="Star", limit=10
        )

        assert len(poster_result["movies"]) > 0
        # Should only include movies with posters and "Star" in the title
        assert all("Star" in movie["title"] for movie in poster_result["movies"])
        assert all(movie["poster_url"] for movie in poster_result["movies"])


def test_reviewed_filter_returns_all_tagged(app, test_user, test_movies) -> None:
    """Reviewed mode returns every movie with a decision, regardless of which."""
    with app.app_context():
        result = get_movies_based_on_filter(user=test_user, mode="reviewed", limit=10)

        # Fixture tags movies 1-5 (3 approve, 2 disapprove)
        assert len(result["movies"]) == 5
        assert all(movie["decision"] for movie in result["movies"])


def test_get_pending_count(app, test_user, test_movies) -> None:
    """Pending count matches untagged, IMDB-linked upcoming movies."""
    with app.app_context():
        # Fixture movies have no imdb_id, and the count mirrors the
        # browse list, which requires one
        assert get_pending_count(test_user) == 0

        # Link two untagged movies (6, 7) and one tagged movie (1) to IMDB
        from app.models.movie import Movie

        for movie_id in (1, 6, 7):
            movie = db.session.get(Movie, movie_id)
            assert movie is not None
            movie.imdb_id = f"tt000000{movie_id}"
        db.session.commit()

        assert get_pending_count(test_user) == 2


def test_user_has_any_tags(app, test_user, test_movies) -> None:
    """user_has_any_tags reflects whether any UserMovie rows exist."""
    from app.models.user import User

    with app.app_context():
        assert user_has_any_tags(test_user) is True

        fresh_user = User(email=None, region="US", language="en")
        db.session.add(fresh_user)
        db.session.commit()
        assert user_has_any_tags(fresh_user) is False
