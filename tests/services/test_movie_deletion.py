from datetime import UTC, datetime
from unittest.mock import patch

from app.errors import TMDbAPIError
from app.extensions import db
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.notification import Notification
from app.models.notification_channel import NotificationChannel
from app.models.tmdb_genre import MovieGenre, TmdbGenre
from app.models.user import User
from app.models.user_movie import UserMovie
from app.services.tmdb_service import check_movie_information


def test_movie_deletion_on_404(app) -> None:
    """Test that a movie is deleted when
    TMDb returns 404, along with all related data."""
    with app.app_context():
        # 1. Setup: Create a movie with various related records
        movie_id = 12345

        # Create the user and notification channel required by FK constraints
        user = User(
            display_name="Test User",
            email="del@example.com",
            region="US",
            language="en",
        )
        db.session.add(user)
        db.session.flush()

        channel = NotificationChannel(user_id=user.id, mode="push", enabled=True)
        channel.days_in_advance = [1, 3, 7]
        db.session.add(channel)
        db.session.flush()

        movie = Movie(
            id=movie_id,
            original_title="Test Movie",
            popularity=10.0,
            original_language="en",
            info_update_at=None,  # Force update
        )
        db.session.add(movie)

        # Add genre
        genre = TmdbGenre(id=1)
        db.session.add(genre)
        movie_genre = MovieGenre(movie_id=movie_id, genre_id=1)
        db.session.add(movie_genre)

        # Add region info
        region_info = MovieRegionInfo(
            movie_id=movie_id, region="US", release_date=datetime.now(UTC).date()
        )
        db.session.add(region_info)

        # Add language info
        lang_info = MovieLanguageInfo(
            movie_id=movie_id, language="en", title="Test Movie"
        )
        db.session.add(lang_info)

        # Add user movie decision
        user_movie = UserMovie(user_id=user.id, movie_id=movie_id, decision="approve")
        db.session.add(user_movie)

        # Add notification
        notification = Notification(
            user_id=user.id,
            channel_id=channel.id,
            movie_id=movie_id,
            days_in_advance=1,
            scheduled_at=datetime.now(UTC),
        )
        db.session.add(notification)

        db.session.commit()

        # Verify they exist
        assert db.session.get(Movie, movie_id) is not None
        assert MovieGenre.query.filter_by(movie_id=movie_id).first() is not None
        assert MovieRegionInfo.query.filter_by(movie_id=movie_id).first() is not None
        assert MovieLanguageInfo.query.filter_by(movie_id=movie_id).first() is not None
        assert UserMovie.query.filter_by(movie_id=movie_id).first() is not None
        assert Notification.query.filter_by(movie_id=movie_id).first() is not None

        # 2. Mock TMDb to return 404
        with patch("app.services.tmdb_service.update_movie_details") as mock_update:
            mock_update.side_effect = TMDbAPIError("Not Found", status_code=404)

            # 3. Trigger update
            check_movie_information(movie)
            # The app code calls db.session.delete(movie)
            # but it doesn't commit immediately.
            # CASCADE ondelete="CASCADE" in DB only works
            # on commit/flush if the DB supports it.
            # SQLAlchemy's cascade="all, delete-orphan" on
            # relationships works when objects are loaded.

            # Let's see if the movie is deleted from session
            assert (
                movie in db.session.deleted or db.session.get(Movie, movie_id) is None
            )

            db.session.commit()

        # Clear the session to ensure we are not seeing cached objects
        db.session.expunge_all()

        # 4. Verify everything is deleted
        assert db.session.get(Movie, movie_id) is None
        assert MovieGenre.query.filter_by(movie_id=movie_id).first() is None
        assert MovieRegionInfo.query.filter_by(movie_id=movie_id).first() is None
        assert MovieLanguageInfo.query.filter_by(movie_id=movie_id).first() is None
        assert UserMovie.query.filter_by(movie_id=movie_id).first() is None
        assert Notification.query.filter_by(movie_id=movie_id).first() is None
