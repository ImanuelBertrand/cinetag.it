from datetime import datetime

from app.extensions import db


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    channel_id = db.Column(db.Integer, db.ForeignKey("notification_channels.id"))
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"))
    days_in_advance = db.Column(db.Integer, nullable=False)
    is_sent = db.Column(db.Boolean, default=False)
    scheduled_at = db.Column(db.DateTime)
    sent_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    channel = db.relationship("NotificationChannel", back_populates="notifications")
    user = db.relationship("User", back_populates="notifications")
    movie = db.relationship("Movie", back_populates="notifications")

    def __init__(self, user_id, channel_id, movie_id, days_in_advance, scheduled_at):
        self.user_id = user_id
        self.channel_id = channel_id
        self.movie_id = movie_id
        self.days_in_advance = days_in_advance
        self.scheduled_at = scheduled_at
