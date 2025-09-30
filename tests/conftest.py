from datetime import datetime, timedelta

import pytest

from app.create_app import create_app
from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.user import User
from app.models.user_movie import UserMovie


@pytest.fixture
def app():
    """Create and configure a Flask app for testing."""
    app = create_app("testing")

    # Check if we're running in Docker by looking for the CONFIG_FILE environment variable
    import os

    if not os.environ.get(
        "CONFIG_FILE"
    ) or "docker-config-test.yaml" not in os.environ.get("CONFIG_FILE"):
        # If not running in Docker, use in-memory SQLite
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"

    app.config["TESTING"] = True

    with app.app_context():
        db.create_all()
        yield app
        # Clean up by removing the session and dropping all tables
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def clean_test_db(app):
    with app.app_context():
        # Only run this cleanup if we're using a real database, not in-memory SQLite
        if not app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///:memory:"):
            # Drop all tables and recreate them
            db.drop_all()
            db.create_all()


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create a test user."""
    with app.app_context():
        # First, clean up any existing test users to avoid duplicate email errors
        User.query.filter(User.email.like("test%@example.com")).delete()
        db.session.commit()

        # Create a new user with a unique email
        import uuid

        unique_id = str(uuid.uuid4())[:8]
        user = User(
            name="Test User",
            email=f"test{unique_id}@example.com",
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.commit()

        # Refresh the user to ensure it's attached to the session
        user_id = user.id
        db.session.expunge_all()  # Clear the session
        user = db.session.get(User, user_id)  # Re-fetch the user

        yield user  # Use yield instead of return to keep the context active

        # Clean up
        db.session.rollback()


@pytest.fixture
def test_movies(app, test_user):
    """Create test movies with different titles."""
    with app.app_context():
        today = datetime.now().date()

        # Create movies with different titles
        movie_ids = []
        for i in range(30):  # Create 30 movies for pagination testing
            # Every 5th movie will have "Star" in the title
            has_star = i % 5 == 0
            title = f"Star Movie {i}" if has_star else f"Regular Movie {i}"

            movie = Movie(
                id=i + 1,
                original_title=title,
                popularity=float(i),
                original_language="en",
            )
            db.session.add(movie)

            # Add region info (release dates spread across next 30 days)
            region_info = MovieRegionInfo(
                movie_id=i + 1, region="US", release_date=today + timedelta(days=i)
            )
            db.session.add(region_info)

            # Add language info
            lang_info = MovieLanguageInfo(
                movie_id=i + 1,
                language="en",
                title=title,
                overview=f"Overview for {title}",
                poster_path=f"/path/to/poster/{i + 1}.jpg",
            )
            db.session.add(lang_info)

            movie_ids.append(i + 1)

        # Add user decisions for some movies
        for i in range(5):
            user_movie = UserMovie(
                user_id=test_user.id,
                movie_id=i + 1,
                decision="approve" if i % 2 == 0 else "disapprove",
            )
            db.session.add(user_movie)

        db.session.commit()

        # Refresh the session to ensure all objects are attached
        db.session.expunge_all()
        movies = [db.session.get(Movie, movie_id) for movie_id in movie_ids]

        yield movies

        # Clean up
        db.session.rollback()
