from datetime import datetime

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    new_email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=True)
    region = db.Column(db.String(2), nullable=True, default="US")
    language = db.Column(db.String(5), nullable=True, default="en")
    temporary_user_id = db.Column(db.Integer, nullable=True)
    password_reset_token = db.Column(db.String(32), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
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
        from app.models.user_calendar import UserCalendar

        # Reset or create calendars using the UserCalendar model
        UserCalendar.reset_hash(self.id, "wanted")
        UserCalendar.reset_hash(self.id, "maybe")
        UserCalendar.reset_hash(self.id, "all")

        return self
