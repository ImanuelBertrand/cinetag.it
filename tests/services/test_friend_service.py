from app.extensions import db
from app.models.friendship import Friendship
from app.models.user import User
from app.models.user_movie import UserMovie
from app.services.user_service import get_movies_based_on_filter


def test_get_movies_based_on_friend_filter(app, test_user, test_movies):
    """Test filtering movies based on a friend's decisions."""
    with app.app_context():
        # 1. Create a friend
        friend = User(display_name="Friend", email="friend@example.com")
        db.session.add(friend)
        db.session.commit()
        friend_id = friend.id

        # 2. Establish friendship
        friendship = Friendship.create_friendship(test_user.id, friend_id)
        db.session.add(friendship)
        db.session.commit()

        # 3. Friend approves some movies
        # Let's say friend approves movie 10, 11 and disapproves 12
        um10 = UserMovie(user_id=friend_id, movie_id=10, decision="approve")
        um11 = UserMovie(user_id=friend_id, movie_id=11, decision="approve")
        um12 = UserMovie(user_id=friend_id, movie_id=12, decision="disapprove")

        db.session.add_all([um10, um11, um12])
        db.session.commit()

        # 4. Filter movies based on this friend
        # In test_movies fixture, movies have IDs 1 to 30.
        # MovieRegionInfo and MovieLanguageInfo are also created for them.

        result = get_movies_based_on_filter(
            user=test_user, mode="all", friend_id=friend_id, limit=10
        )

        # Should only return movies 10 and 11 (approved by friend)
        assert len(result["movies"]) == 2
        movie_ids = [m["id"] for m in result["movies"]]
        assert 10 in movie_ids
        assert 11 in movie_ids
        assert 12 not in movie_ids


def test_get_movies_based_on_friend_filter_no_decisions(app, test_user, test_movies):
    """Test filtering movies based on a friend who hasn't approved anything."""
    with app.app_context():
        friend = User(display_name="Lazy Friend", email="lazy@example.com")
        db.session.add(friend)
        db.session.commit()
        friend_id = friend.id

        # Establish friendship
        friendship = Friendship.create_friendship(test_user.id, friend_id)
        db.session.add(friendship)
        db.session.commit()

        result = get_movies_based_on_filter(
            user=test_user, mode="all", friend_id=friend_id, limit=10
        )

        assert len(result["movies"]) == 0
