from datetime import datetime
from typing import List

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=True)
    email_confirmed = db.Column(db.Boolean, default=False)
    region = db.Column(db.String(2), nullable=True)
    language = db.Column(db.String(5), nullable=True)
    is_temporary = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user_movies = db.relationship(
        "UserMovie", back_populates="user", cascade="all, delete-orphan"
    )


class Movie(db.Model):
    __tablename__ = "movies"

    id = db.Column(db.Integer, primary_key=True)
    original_title = db.Column(db.String(255), nullable=False)

    region_info = db.relationship(
        "MovieRegionInfo", back_populates="movie", cascade="all, delete-orphan"
    )
    language_info = db.relationship(
        "MovieLanguageInfo", back_populates="movie", cascade="all, delete-orphan"
    )

    user_movies = db.relationship(
        "UserMovie", back_populates="movie", cascade="all, delete-orphan"
    )

    def update_from_tmdb(self, data: dict) -> bool:
        updated = False
        if self.original_title != data["original_title"]:
            self.original_title = data["original_title"]
            updated = True
        return updated

    @staticmethod
    def create_from_tmdb(data: dict) -> "Movie":
        return Movie(
            id=data["id"],
            original_title=data["original_title"],
        )

    @staticmethod
    def get_upcoming_movies(region, language) -> "List[Movie]":
        from app.services.movie_service import sync_upcoming_movies

        return sync_upcoming_movies(region, language)


class MovieRegionInfo(db.Model):
    __tablename__ = "movie_region_info"

    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    region = db.Column(db.String(2), nullable=False)
    release_date = db.Column(db.Date, nullable=False)

    movie = db.relationship("Movie", back_populates="region_info")

    @staticmethod
    def create_from_tmdb(data: dict, region: str) -> "MovieRegionInfo":
        return MovieRegionInfo(
            movie_id=data["id"],
            region=region,
            release_date=datetime.strptime(data["release_date"], "%Y-%m-%d"),
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        release_date = datetime.strptime(data["release_date"], "%Y-%m-%d")
        if self.release_date != release_date:
            self.release_date = release_date
            updated = True
        return updated


class MovieLanguageInfo(db.Model):
    __tablename__ = "movie_language_info"

    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    language = db.Column(db.String(5), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    poster_path = db.Column(db.String(255), nullable=True)
    overview = db.Column(db.Text, nullable=True)

    movie = db.relationship("Movie", back_populates="language_info")

    @staticmethod
    def create_from_tmdb(data: dict, language: str) -> "MovieLanguageInfo":
        return MovieLanguageInfo(
            movie_id=data["id"],
            language=language,
            title=data["title"],
            poster_path=data["poster_path"],
            overview=data["overview"],
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        if self.title != data["title"]:
            self.title = data["title"]
            updated = True
        if self.poster_path != data["poster_path"]:
            self.poster_path = data["poster_path"]
            updated = True
        if self.overview != data["overview"]:
            self.overview = data["overview"]
            updated = True
        return updated


class UserMovie(db.Model):
    __tablename__ = "user_movies"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    decision = db.Column(
        db.String(10), nullable=False
    )  # 'approve' or 'disapprove'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = db.relationship("User", back_populates="user_movies")
    movie = db.relationship("Movie", back_populates="user_movies")
