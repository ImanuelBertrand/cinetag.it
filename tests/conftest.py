import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from collections.abc import Generator
from sqlalchemy import text

from app.create_app import create_app
from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.user import User
from app.models.user_movie import UserMovie


def _drop_pg_enums() -> None:
    """Drop all user-defined PostgreSQL ENUM types (which drop_all() skips)."""
    with db.engine.connect() as conn:
        conn.execute(
            text(
                "DO $$ DECLARE r RECORD; BEGIN "
                "FOR r IN ("
                "  SELECT typname FROM pg_type "
                "  JOIN pg_namespace ON pg_type.typnamespace = pg_namespace.oid "
                "  WHERE typtype = 'e' AND nspname = 'public'"
                ") LOOP "
                "  EXECUTE 'DROP TYPE IF EXISTS ' "
                "|| quote_ident(r.typname) || ' CASCADE'; "
                "END LOOP; END $$;"
            )
        )
        conn.commit()


@pytest.fixture(scope="session")
def app():
    """Create and configure a Flask app once for the entire test session."""
    app = create_app("testing")
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()
        _drop_pg_enums()


@pytest.fixture(autouse=True)
def clean_test_db(app) -> Generator[None]:
    """Delete all rows between tests. Schema is created once per session."""
    yield
    db.session.rollback()
    for table in reversed(db.metadata.sorted_tables):
        db.session.execute(table.delete())
    db.session.commit()
    db.session.remove()


@pytest.fixture(autouse=True)
def _disable_rate_limiter(app) -> Generator[None]:
    """Keep the rate limiter off for the bulk of the suite (tests share a single
    client IP and would otherwise trip the global limit). The limiter is enabled
    at app init so its hook is registered; the dedicated rate-limit tests flip
    ``limiter.enabled`` back on. Storage is reset each test for isolation."""
    import contextlib

    from app.extensions import limiter

    limiter.enabled = False
    with contextlib.suppress(Exception):
        limiter.reset()
    yield
    limiter.enabled = False


@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()


@pytest.fixture
def test_user(app):
    """Create a test user."""
    user = User(
        display_name="Test User",
        email=f"test{str(uuid.uuid4())[:8]}@example.com",
        region="US",
        language="en",
    )
    db.session.add(user)
    db.session.commit()
    db.session.refresh(user)
    return user


@pytest.fixture
def test_movies(app, test_user):
    """Create test movies with different titles."""
    today = datetime.now(UTC).date()

    movie_ids = []
    for i in range(30):  # Create 30 movies for pagination testing
        has_star = i % 5 == 0
        title = f"Star Movie {i}" if has_star else f"Regular Movie {i}"

        movie = Movie(
            id=i + 1,
            original_title=title,
            popularity=float(i),
            original_language="en",
        )
        db.session.add(movie)

        region_info = MovieRegionInfo(
            movie_id=i + 1, region="US", release_date=today + timedelta(days=i)
        )
        db.session.add(region_info)

        lang_info = MovieLanguageInfo(
            movie_id=i + 1,
            language="en",
            title=title,
            overview=f"Overview for {title}",
            poster_path=f"/path/to/poster/{i + 1}.jpg",
        )
        db.session.add(lang_info)

        movie_ids.append(i + 1)

    for i in range(5):
        user_movie = UserMovie(
            user_id=test_user.id,
            movie_id=i + 1,
            decision="approve" if i % 2 == 0 else "disapprove",
        )
        db.session.add(user_movie)

    db.session.commit()
    return [db.session.get(Movie, movie_id) for movie_id in movie_ids]
