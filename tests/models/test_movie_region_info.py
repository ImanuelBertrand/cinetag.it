from datetime import UTC, date, datetime

from app.extensions import db
from app.models.movie import Movie
from app.models.movie_region_info import MovieRegionInfo


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


def test_create_from_tmdb(app) -> None:
    """Test MovieRegionInfo.create_from_tmdb creates correct instance."""
    with app.app_context():
        _create_movie(app, 400)

        release_date = date(2025, 6, 15)
        region_info = MovieRegionInfo.create_from_tmdb(400, "US", release_date)

        assert region_info.movie_id == 400
        assert region_info.region == "US"
        assert region_info.release_date == release_date


def test_update_from_tmdb_no_changes(app) -> None:
    """Test MovieRegionInfo.update_from_tmdb returns False when nothing changes."""
    with app.app_context():
        _create_movie(app, 401)

        release_date = date(2025, 6, 15)
        region_info = MovieRegionInfo(
            movie_id=401,
            region="US",
            release_date=release_date,
        )
        db.session.add(region_info)
        db.session.commit()

        updated = region_info.update_from_tmdb(release_date)
        assert updated is False


def test_update_from_tmdb_with_date_change(app) -> None:
    """Test MovieRegionInfo.update_from_tmdb returns True when date changes."""
    with app.app_context():
        _create_movie(app, 402)

        old_date = date(2025, 6, 15)
        new_date = date(2025, 7, 20)

        region_info = MovieRegionInfo(
            movie_id=402,
            region="US",
            release_date=old_date,
        )
        db.session.add(region_info)
        db.session.commit()

        updated = region_info.update_from_tmdb(new_date)
        assert updated is True
        assert region_info.release_date == new_date


def test_update_from_tmdb_clears_is_fake(app) -> None:
    """Test MovieRegionInfo.update_from_tmdb clears is_fake flag."""
    with app.app_context():
        _create_movie(app, 403)

        release_date = date(2025, 6, 15)
        region_info = MovieRegionInfo(
            movie_id=403,
            region="US",
            release_date=release_date,
            is_fake=True,
        )
        db.session.add(region_info)
        db.session.commit()

        # Same date but is_fake should be cleared
        updated = region_info.update_from_tmdb(release_date)
        assert updated is True
        assert region_info.is_fake is False


def test_repr(app) -> None:
    """Test MovieRegionInfo __repr__."""
    with app.app_context():
        _create_movie(app, 404)

        region_info = MovieRegionInfo(
            movie_id=404,
            region="GB",
            release_date=datetime.now(UTC).date(),
        )
        db.session.add(region_info)
        db.session.commit()

        assert "404" in repr(region_info)
        assert "GB" in repr(region_info)
