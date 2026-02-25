import secrets
from datetime import UTC, datetime

from app.extensions import db


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

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    calendar_type = db.Column(
        db.String(10), nullable=False
    )  # 'wanted', 'maybe', or 'all'
    calendar_hash = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )

    user = db.relationship("User", back_populates="calendars")

    __table_args__ = (
        db.Index("user_calendar_idx", "user_id", "calendar_type", unique=True),
    )

    @classmethod
    def generate_hash(cls):
        """Generate a new random hash for a calendar URL"""
        return secrets.token_hex(32)

    @classmethod
    def get_or_create(cls, user_id, calendar_type):
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
    def reset_hash(cls, user_id, calendar_type):
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
