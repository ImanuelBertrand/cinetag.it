import secrets
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Self

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class UserCalendar(db.Model):
    """
    Model representing a calendar for a user.

    Each user can have multiple calendars of different types:
    - 'wanted': Calendar for movies the user wants to see
    - 'maybe': Calendar for movies the user might want to see
    - 'all': Calendar for all movies the user is interested in

    Each calendar has a unique hash that is used in the calendar URL.
    """

    __tablename__ = "user_calendars"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    calendar_type: Mapped[str] = mapped_column(
        String(10)
    )  # 'wanted', 'maybe', or 'all'
    calendar_hash: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship(back_populates="calendars")

    __table_args__ = (
        Index("user_calendar_idx", "user_id", "calendar_type", unique=True),
    )

    @classmethod
    def generate_hash(cls) -> str:
        """Generate a new random hash for a calendar URL"""
        return secrets.token_hex(32)

    @classmethod
    def get_or_create(cls, user_id, calendar_type) -> Self:
        """
        Get an existing calendar or create a new one if it doesn't exist.

        Args:
            user_id: The ID of the user
            calendar_type: The type of calendar ('wanted', 'maybe', or 'all')

        Returns:
            A UserCalendar object
        """
        calendar = cls.query.filter_by(
            user_id=user_id, calendar_type=calendar_type
        ).first()

        if not calendar:
            calendar = cls(
                user_id=user_id,
                calendar_type=calendar_type,
                calendar_hash=cls.generate_hash(),
            )
            db.session.add(calendar)

        return calendar

    @classmethod
    def reset_hash(cls, user_id, calendar_type) -> Self:
        """
        Reset the hash for a specific calendar.

        Args:
            user_id: The ID of the user
            calendar_type: The type of calendar ('wanted', 'maybe', or 'all')

        Returns:
            The updated UserCalendar object
        """
        calendar = cls.get_or_create(user_id, calendar_type)
        calendar.calendar_hash = cls.generate_hash()
        return calendar
