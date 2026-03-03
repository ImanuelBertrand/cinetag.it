from datetime import UTC, datetime

from app.extensions import db
from app.models.user import User


class Friendship(db.Model):
    """
    Represents a bidirectional friendship between two users.

    This model stores connections between users. A single record represents
    a mutual friendship between two users. The relationship is not directional,
    so the order of user1_id and user2_id doesn't matter semantically.

    To maintain consistency and prevent duplicate records, we enforce that
    user1_id is always the lower ID value and user2_id is the higher ID value.
    """

    __tablename__ = "friendships"

    id = db.Column(db.Integer, primary_key=True)
    # Always the lower user ID of the two friends
    user1_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    # Always the higher user ID of the two friends
    user2_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    # Relationships to the User model
    user1 = db.relationship(
        "User",
        foreign_keys=[user1_id],
        backref=db.backref("friendships_as_user1", lazy="dynamic"),
    )
    user2 = db.relationship(
        "User",
        foreign_keys=[user2_id],
        backref=db.backref("friendships_as_user2", lazy="dynamic"),
    )

    __table_args__ = (
        # Ensure uniqueness of the friendship pair
        db.Index("friendship_idx", "user1_id", "user2_id", unique=True),
        # Enforce user1_id < user2_id
        db.CheckConstraint("user1_id < user2_id", name="check_user_order"),
    )

    @classmethod
    def create_friendship(cls, user_a_id: int, user_b_id: int):
        """
        Create a friendship between two users, ensuring the correct order of IDs.

        Args:
            user_a_id: ID of the first user
            user_b_id: ID of the second user

        Returns:
            Friendship: A new Friendship object with user IDs in the correct order
        """
        # Ensure user1_id is the lower ID and user2_id is the higher ID
        if user_a_id < user_b_id:
            return cls(user1_id=user_a_id, user2_id=user_b_id)
        return cls(user1_id=user_b_id, user2_id=user_a_id)

    @classmethod
    def get_friendship(cls, user_a_id: int, user_b_id: int):
        """
        Get the friendship between two users, if it exists.

        Args:
            user_a_id: ID of the first user
            user_b_id: ID of the second user

        Returns:
            Friendship: The friendship object, or None if no friendship exists
        """
        # Determine the correct order of user IDs
        if user_a_id < user_b_id:
            user1_id, user2_id = user_a_id, user_b_id
        else:
            user1_id, user2_id = user_b_id, user_a_id

        # Query the friendship
        friendship = cls.query.filter_by(user1_id=user1_id, user2_id=user2_id).first()

        # Defensive programming: fallback to check with users switched
        # This shouldn't happen due to our ordering logic, but just in case
        if friendship is None:
            friendship = cls.query.filter_by(
                user1_id=user2_id, user2_id=user1_id
            ).first()

        return friendship

    @classmethod
    def get_friends_of_user(cls, user_id: int) -> set[int]:
        """
        Get all friends of a user.

        Args:
            user_id: ID of the user

        Returns:
            set: Set of user IDs who are friends with the specified user
        """
        # Query friendships where the user is either user1 or user2
        friendships = cls.query.filter(
            db.or_(cls.user1_id == user_id, cls.user2_id == user_id)
        ).all()

        # Extract the friend IDs (the other user in each friendship)
        friend_ids = set()
        for friendship in friendships:
            if friendship.user1_id == user_id:
                friend_ids.add(friendship.user2_id)
            else:
                friend_ids.add(friendship.user1_id)

        return friend_ids

    @classmethod
    def get_friends_with_details(cls, user_id: int):
        """
        Get all friends of a user with their details in a single query.
        This is more efficient than querying each friend separately.

        Args:
            user_id: ID of the user

        Returns:
            list: List of dictionaries containing friend details
        """
        # Query all friendships and join with the User table to get friend details
        # We need to use two separate queries for user1 and user2 cases

        # Case 1: user is user1, friend is user2
        query1 = (
            db.session.query(cls, User)
            .join(User, User.id == cls.user2_id)
            .filter(cls.user1_id == user_id)
        )

        # Case 2: user is user2, friend is user1
        query2 = (
            db.session.query(cls, User)
            .join(User, User.id == cls.user1_id)
            .filter(cls.user2_id == user_id)
        )

        # Combine the results
        results = []

        for friendship, friend in query1.all():
            results.append(
                {
                    "id": friend.id,
                    "name": friend.display_name or "Friend",
                    "created_at": friendship.created_at.isoformat()
                    if friendship.created_at
                    else None,
                }
            )

        for friendship, friend in query2.all():
            results.append(
                {
                    "id": friend.id,
                    "name": friend.display_name or "Friend",
                    "created_at": friendship.created_at.isoformat()
                    if friendship.created_at
                    else None,
                }
            )

        return results
