from datetime import datetime

from app.extensions import db


class FriendRequest(db.Model):
    __tablename__ = "friend_requests"

    id = db.Column(db.Integer, primary_key=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(
        db.String(20), nullable=False, default="pending"
    )  # pending, accepted, rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    requester = db.relationship(
        "User",
        foreign_keys=[requester_id],
        backref=db.backref("sent_friend_requests", lazy="dynamic"),
    )
    recipient = db.relationship(
        "User",
        foreign_keys=[recipient_id],
        backref=db.backref("received_friend_requests", lazy="dynamic"),
    )

    __table_args__ = (
        db.Index("friend_request_idx", "requester_id", "recipient_id", unique=True),
    )
