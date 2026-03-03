from datetime import UTC, datetime

from app.extensions import db


class NotificationChannel(db.Model):
    __tablename__ = "notification_channels"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    enabled = db.Column(db.Integer)
    days_in_advance = db.Column(db.JSON, nullable=False)
    mode = db.Column(
        db.Enum("email", "push", name="user_notification_mode"), nullable=False
    )
    notification_data = db.Column(db.JSON, nullable=True)
    include_maybe_movies = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now(UTC))
    updated_at = db.Column(
        db.DateTime, default=datetime.now(UTC), onupdate=datetime.now(UTC)
    )

    user = db.relationship("User", back_populates="notification_channels")
    notifications = db.relationship(
        "Notification", back_populates="channel", cascade="all, delete-orphan"
    )

    @staticmethod
    def get_valid_types() -> list[str]:
        return ["email", "push"]

    def __init__(self, user_id: int, mode: str, enabled: bool) -> None:
        self.user_id = user_id
        self.mode = mode
        self.enabled = enabled
