from datetime import datetime

from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    request_id = db.Column(db.Integer, db.ForeignKey("notification_requests.id"))
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"))
    days_in_advance = db.Column(db.Integer, nullable=False)
    sent = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    request = db.relationship(
        "NotificationRequest", back_populates="notifications"
    )

    def __init__(self, user_id, request_id, movie_id, days_in_advance):
        self.user_id = user_id
        self.request_id = request_id
        self.movie_id = movie_id
        self.days_in_advance = days_in_advance
