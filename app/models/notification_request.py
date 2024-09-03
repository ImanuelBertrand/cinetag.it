from datetime import datetime

from app.extensions import db


class NotificationRequest(db.Model):
    __tablename__ = "notification_requests"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    days_in_advance = db.Column(db.JSON, nullable=False)
    notification_type = db.Column(db.Enum("email", "push"), nullable=False)
    notification_data = db.Column(db.JSON, nullable=True)
    include_maybe_movies = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # user = db.relationship("User", back_populates="notification_requests")
    notifications = db.relationship(
        "Notification", back_populates="request", cascade="all, delete-orphan"
    )

    def __init__(self, user_id, notification_type, notification_data):
        self.user_id = user_id
        self.notification_type = notification_type
        self.notification_data = notification_data
