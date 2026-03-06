from datetime import UTC, datetime, timedelta

import jwt
import pytest
from flask import current_app

from app.errors import UserFeedbackError
from app.extensions import db
from app.models.movie import Movie
from app.services.user_service import (
    confirm_user_email,
    get_movies_based_on_filter,
)


def test_confirm_user_email_invalid_token(app):
    with app.app_context():
        token = jwt.encode(
            {
                "confirmation": 9999,
                "new_mail": "bad@example.com",
                "exp": datetime.now(UTC) + timedelta(hours=24),
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        with pytest.raises(UserFeedbackError, match="User not found"):
            confirm_user_email(token)


def test_confirm_user_email_expired_token(app):
    with app.app_context():
        token = jwt.encode(
            {
                "confirmation": 1,
                "new_mail": "new@example.com",
                "exp": datetime.now(UTC) - timedelta(hours=1),
            },
            current_app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        with pytest.raises(
            UserFeedbackError, match="The confirmation link has expired"
        ):
            confirm_user_email(token)


def test_get_movies_based_on_filter_advanced(app, test_user, test_movies):
    with app.app_context():
        # Test need_imdb=True (our test_movies don't have imdb_id by default)
        result = get_movies_based_on_filter(user=test_user, mode="all", need_imdb=True)
        assert len(result["movies"]) == 0

        # Manually add imdb_id to one movie and make it release in the future
        movie_id = test_movies[0].id
        movie = db.session.get(Movie, movie_id)
        movie.imdb_id = "tt1234567"

        from app.models.movie_region_info import MovieRegionInfo

        mri = MovieRegionInfo.query.filter_by(movie_id=movie.id, region="US").first()
        if mri:
            mri.release_date = datetime.now(UTC).date() + timedelta(days=1)

        # In test_movies fixture, movie with id 1 is "Star Movie 0"
        # It has language info for "en" and title "Star Movie 0"
        # Our test_user has region "US" and language "en"

        db.session.commit()

        # The query in get_movies_based_on_filter has:
        # .filter(MovieRegionInfo.release_date >= datetime.now().date())
        # Since we set release_date to tomorrow, it should be included.

        result = get_movies_based_on_filter(user=test_user, mode="all", need_imdb=True)
        assert len(result["movies"]) == 1
        assert result["movies"][0]["id"] == movie.id
