from app.extensions import db


class UserEmailQueue(db.Model):
    # Table to store pending emails for async email confirmation / PW reset
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mail_type = db.Column(db.String(10), nullable=False)

    user = db.relationship("User", backref="pending_emails")
