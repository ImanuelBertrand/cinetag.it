from datetime import datetime

from app.services.user_service import get_movies_based_on_filter


def test_name_filter_with_pagination(app, test_user, test_movies):
    """Test that name filter works correctly with pagination."""
    with app.app_context():
        # Test case 1: First page with name filter
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

        # Test case 2: Pagination with name filter
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


def test_name_filter_with_other_filters(app, test_user, test_movies):
    """Test that name filter works correctly with other filters."""
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
