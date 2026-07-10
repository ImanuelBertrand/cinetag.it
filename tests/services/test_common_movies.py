"""Phase 3b: the friend filter composes with decision modes so that
`approved` + friend_id is the true intersection, while `all` + friend_id is
everything the friend approved."""

from datetime import UTC, datetime, timedelta

from app.extensions import db
from app.models.friendship import Friendship
from app.models.movie import Movie
from app.models.movie_language_info import MovieLanguageInfo
from app.models.movie_region_info import MovieRegionInfo
from app.models.user import User
from app.models.user_movie import UserMovie
from app.services.user_service import get_movies_based_on_filter


def _make_movie(movie_id):
    release_date = datetime.now(UTC).date() + timedelta(days=5)
    title = f"Movie {movie_id}"
    db.session.add(
        Movie(
            id=movie_id,
            original_title=title,
            popularity=1.0,
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
            overview="o",
            poster_path=f"/p/{movie_id}.jpg",
        )
    )


def test_common_movies_vs_friend_picks(app, test_user) -> None:
    with app.app_context():
        me = db.session.get(User, test_user.id)
        assert me is not None
        friend = User(
            display_name="Friend", email="f@example.com", region="US", language="en"
        )
        db.session.add(friend)
        db.session.commit()

        db.session.add(Friendship.create_friendship(me.id, friend.id))

        for mid in (1, 2, 3, 4):
            _make_movie(mid)

        # m1: both approve; m2: I approve, friend disapprove;
        # m3: friend approve only; m4: I approve only
        db.session.add(UserMovie(user_id=me.id, movie_id=1, decision="approve"))
        db.session.add(UserMovie(user_id=friend.id, movie_id=1, decision="approve"))
        db.session.add(UserMovie(user_id=me.id, movie_id=2, decision="approve"))
        db.session.add(UserMovie(user_id=friend.id, movie_id=2, decision="disapprove"))
        db.session.add(UserMovie(user_id=friend.id, movie_id=3, decision="approve"))
        db.session.add(UserMovie(user_id=me.id, movie_id=4, decision="approve"))
        db.session.commit()

        # "Common Movies": approved mode + friend => intersection of approvals
        common = get_movies_based_on_filter(
            user=me, mode="approved", friend_id=friend.id, limit=10
        )
        assert {m["id"] for m in common["movies"]} == {1}

        # "Their picks": all mode + friend => everything the friend approved
        picks = get_movies_based_on_filter(
            user=me, mode="all", friend_id=friend.id, limit=10
        )
        assert {m["id"] for m in picks["movies"]} == {1, 3}
