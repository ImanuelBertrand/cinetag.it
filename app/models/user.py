from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import sqlalchemy
import sqlalchemy.exc
from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.user_calendar import UserCalendar
from app.utils.friend_code import generate_friend_code

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.notification_channel import NotificationChannel
    from app.models.user_movie import UserMovie


class User(db.Model):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    # User's display name, used throughout the application
    display_name: Mapped[str | None] = mapped_column(String(200))
    # Unique code for adding friends, only for registered users
    friend_code: Mapped[str | None] = mapped_column(String(64), unique=True)
    email: Mapped[str | None] = mapped_column(String(120), unique=True)
    new_email: Mapped[str | None] = mapped_column(String(120), unique=True)
    password: Mapped[str | None] = mapped_column(String(255))
    region: Mapped[str | None] = mapped_column(String(2), default="US")
    language: Mapped[str | None] = mapped_column(String(5), default="en")
    # Relationship to a temporary user (if the user liked a move before logging in)
    temporary_user_id: Mapped[int | None] = mapped_column()
    password_reset_token: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user_movies: Mapped[list[UserMovie]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    calendars: Mapped[list[UserCalendar]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    notification_channels: Mapped[list[NotificationChannel]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
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
