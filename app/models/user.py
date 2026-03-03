from datetime import UTC, datetime

import sqlalchemy

from app.extensions import db
from app.models.user_calendar import UserCalendar
from app.utils.friend_code import generate_friend_code


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    # User's display name, used throughout the application
    display_name = db.Column(db.String(200), nullable=True)
    # Unique code for adding friends, only for registered users
    friend_code = db.Column(db.String(64), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    new_email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(255), nullable=True)
    region = db.Column(db.String(2), nullable=True, default="US")
    language = db.Column(db.String(5), nullable=True, default="en")
    # Relationship to a temporary user (if the user liked a move before logging in)
    temporary_user_id = db.Column(db.Integer, nullable=True)
    password_reset_token = db.Column(db.String(32), nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user_movies = db.relationship(
        "UserMovie", back_populates="user", cascade="all, delete-orphan"
    )

    calendars = db.relationship(
        "UserCalendar", back_populates="user", cascade="all, delete-orphan"
    )

    notification_channels = db.relationship(
        "NotificationChannel", back_populates="user", cascade="all, delete-orphan"
    )
    notifications = db.relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )

    def reset_calendar_hashes(self):
        """
        Generate new random hashes for calendar URLs

        This method now uses the UserCalendar model to store calendar hashes,
        but also updates the legacy fields for backward compatibility.
        """
        UserCalendar.reset_hash(self.id, "wanted")
        UserCalendar.reset_hash(self.id, "maybe")
        UserCalendar.reset_hash(self.id, "all")

        return self

    def _generate_unique_friend_code(self):
        """
        Helper method to generate a unique friend code.

        Returns:
            str: A unique friend code
        """
        max_attempts = 10  # Reasonable number of attempts

        for _ in range(max_attempts):
            try:
                with db.session.begin_nested():
                    # Generate a new code
                    self.friend_code = generate_friend_code()
                    db.session.add(self)
            except sqlalchemy.exc.IntegrityError:
                continue
            else:
                return self.friend_code

        raise RuntimeError(
            f"Failed to generate a unique friend code after {max_attempts} attempts."
        )

    def ensure_friend_code(self):
        """
        Ensure the user has a friend code.
        If the user doesn't have a friend code, generate one.
        Friend codes are only generated for registered users (non-temporary).

        Returns:
            str: The user's friend code or None if the user is temporary
        """
        # Skip friend code generation for temporary users
        if not self.email:
            return None

        if not self.friend_code:
            return self._generate_unique_friend_code()

        return self.friend_code

    def reset_friend_code(self):
        """
        Generate a new friend code for the user.

        Returns:
            str: The user's new friend code
        """
        return self._generate_unique_friend_code()
