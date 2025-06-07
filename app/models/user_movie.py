from datetime import datetime

from app.extensions import db


class UserMovie(db.Model):
    __tablename__ = "user_movies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    decision = db.Column(db.String(10), nullable=False)  # 'approve' or 'disapprove'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="user_movies")
    movie = db.relationship("Movie", back_populates="user_movies")

    __table_args__ = (db.Index("user_movie_idx", "user_id", "movie_id", unique=True),)
