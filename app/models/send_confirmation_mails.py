from datetime import UTC, datetime

from app.extensions import db


class SentConfirmationMails(db.Model):
    """
    This model exists so that we can avoid sending too many
    confirmation emails to the same address
    """

    __tablename__ = "sent_confirmation_mails"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.now(UTC))
