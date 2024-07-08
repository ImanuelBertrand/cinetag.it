from datetime import datetime
from typing import Dict

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


class UserEmailQueue(db.Model):
    # Table to store pending emails for async email confirmation / PW reset
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    mail_type = db.Column(db.String(10), nullable=False)

    user = db.relationship("User", backref="pending_emails")


class Movie(db.Model):
    __tablename__ = "movies"

    id = db.Column(db.Integer, primary_key=True)
    original_title = db.Column(db.String(255), nullable=False)
    popularity = db.Column(db.Float, nullable=True)
    original_language = db.Column(db.String(2), nullable=True)
    info_update_at = db.Column(db.DateTime, nullable=True)
    imdb_id = db.Column(db.String(20), nullable=True)
    origin_country = db.Column(db.String(2), nullable=True)
    runtime = db.Column(db.Integer, nullable=True)
    spoken_languages = db.Column(db.String(255), nullable=True)

    region_info = db.relationship(
        "MovieRegionInfo", back_populates="movie", cascade="all, delete-orphan"
    )
    language_info = db.relationship(
        "MovieLanguageInfo", back_populates="movie", cascade="all, delete-orphan"
    )

    user_movies = db.relationship(
        "UserMovie", back_populates="movie", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Movie {self.id} ({self.original_title})>"

    def get_localized_data(
        self, lang: str, language_infos: "Dict[str, MovieLanguageInfo]" = None
    ) -> Dict[str, str]:
        if language_infos is None:
            language_infos = {
                lang_info.language: lang_info for lang_info in self.language_info
            }

        langs = [lang, "en", self.original_language]
        info_sources = [language_infos.get(key) for key in langs]
        fields = ["title", "overview", "tagline", "runtime", "poster_path"]
        fallbacks = {"title": self.original_title, "runtime": self.runtime}

        data = {
            field: next(
                (
                    getattr(info_source, field)
                    for info_source in info_sources
                    if info_source and getattr(info_source, field)
                ),
                fallbacks.get(field, ""),
            )
            for field in fields
        }

        return data

    def update_from_tmdb(self, data: dict) -> bool:
        updated = False
        if self.original_title != data["original_title"]:
            self.original_title = data["original_title"]
            updated = True
        if self.popularity != data["popularity"]:
            self.popularity = data["popularity"]
            updated = True
        if self.original_language != data["original_language"]:
            self.original_language = data["original_language"]
            updated = True
        if "runtime" in data and self.runtime != data.get("runtime"):
            self.runtime = data.get("runtime")
            updated = True
        if "imdb_id" in data and self.imdb_id != data.get("imdb_id"):
            self.imdb_id = data.get("imdb_id")
            updated = True

        origin_country = ",".join(data.get("origin_country", []))
        if self.origin_country != origin_country:
            self.origin_country = origin_country
            updated = True

        spoken_languages = ",".join(
            [lang["iso_639_1"] for lang in data.get("spoken_languages", [])]
        )
        if self.spoken_languages != spoken_languages:
            self.spoken_languages = spoken_languages
            updated = True

        return updated

    @staticmethod
    def create_from_tmdb(data: dict) -> "Movie":
        return Movie(
            id=data["id"],
            original_title=data["original_title"],
            popularity=data["popularity"],
            original_language=data["original_language"],
            runtime=data.get("runtime"),
            imdb_id=data.get("imdb_id"),
            origin_country=",".join(data.get("origin_country", [])),
            spoken_languages=",".join(
                [lang["iso_639_1"] for lang in data.get("spoken_languages", [])]
            ),
        )


class MovieRegionInfo(db.Model):
    __tablename__ = "movie_region_info"

    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    region = db.Column(db.String(2), nullable=False)
    release_date = db.Column(db.Date, nullable=False)
    is_fake = db.Column(db.Boolean, default=False)

    movie = db.relationship("Movie", back_populates="region_info")

    __table_args__ = (
        db.Index("movie_region_info_idx", "movie_id", "region"),
        db.Index("movie_region_info_release_date_idx", "release_date"),
    )

    def __repr__(self):
        return f"<MovieRegionInfo {self.movie_id} ({self.region})>"

    @staticmethod
    def create_from_tmdb(movie_id: int, region: str, date) -> "MovieRegionInfo":
        return MovieRegionInfo(
            movie_id=movie_id,
            region=region,
            release_date=date,
        )

    def update_from_tmdb(self, date: datetime.date) -> bool:
        updated = False
        if self.release_date != date:
            self.release_date = date
            updated = True
        if self.is_fake:
            self.is_fake = False
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
    tagline = db.Column(db.String(255), nullable=True)
    runtime = db.Column(db.Integer, nullable=True)

    movie = db.relationship("Movie", back_populates="language_info")

    __table_args__ = (db.Index("movie_language_info_idx", "movie_id", "language"),)

    def __repr__(self):
        return f"<MovieLanguageInfo {self.movie_id} ({self.language})>"

    @staticmethod
    def create_from_tmdb(
        movie_id: int, data: dict, language: str = None
    ) -> "MovieLanguageInfo":
        if language is not None:
            data = {"iso_639_1": language, "data": data}

        return MovieLanguageInfo(
            movie_id=movie_id,
            language=data["iso_639_1"],
            title=data["data"].get("title"),
            overview=data["data"].get("overview"),
            tagline=data["data"].get("tagline"),
            runtime=data["data"].get("runtime"),
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        if self.title != data["title"]:
            self.title = data["title"]
            updated = True

        if "poster_path" in data and self.poster_path != data["poster_path"]:
            self.poster_path = data["poster_path"]
            updated = True

        if self.overview != data["overview"]:
            self.overview = data["overview"]
            updated = True

        if "tagline" in data and self.tagline != data["tagline"]:
            self.tagline = data["tagline"]
            updated = True

        runtime = data.get("runtime", None) or None
        if self.runtime != runtime:
            self.runtime = runtime
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

    __table_args__ = (db.Index("user_movie_idx", "user_id", "movie_id"),)


class TmdbLanguage(db.Model):
    __tablename__ = "tmdb_languages"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), nullable=False, unique=True)
    english_name = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def get_name(self) -> str:
        return self.name or self.english_name

    @staticmethod
    def create_from_tmdb(data: dict) -> "TmdbLanguage":
        return TmdbLanguage(
            code=data["iso_639_1"],
            english_name=data["english_name"],
            name=data["name"]
            if data["name"] and data["name"].replace("?", "")
            else "",
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        if self.english_name != data["english_name"]:
            self.english_name = data["english_name"]
            updated = True
        name = (
            data["name"] if data["name"] and data["name"].replace("?", "") else ""
        )
        if self.name != name:
            self.name = name
            updated = True
        return updated


class TmdbRegion(db.Model):
    __tablename__ = "tmdb_regions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), nullable=False, unique=True)
    english_name = db.Column(db.String(50), nullable=False)
    native_name = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def get_name(self) -> str:
        return self.native_name or self.english_name

    @staticmethod
    def create_from_tmdb(data: dict) -> "TmdbRegion":
        return TmdbRegion(
            code=data["iso_3166_1"],
            english_name=data["english_name"],
            native_name=data["native_name"],
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        if self.english_name != data["english_name"]:
            self.english_name = data["english_name"]
            updated = True
        if self.native_name != data["native_name"]:
            self.native_name = data["native_name"]
            updated = True
        return updated


class MiscData(db.Model):
    __tablename__ = "misc_data"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False, unique=True)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def save(key, value, commit=False):
        data = MiscData.query.filter_by(key=key).first()
        if data:
            data.value = value
        else:
            data = MiscData(key=key, value=value)
        db.session.add(data)
        if commit:
            db.session.commit()

    @staticmethod
    def get(key, default: str = None) -> str:
        data = MiscData.query.filter_by(key=key).first()
        return data.value if data else default

    def __repr__(self):
        return f"<MiscData {self.key}: {self.value}>"


class SentConfirmationMails(db.Model):
    """
    This model exists so that we can avoid sending too many
    confirmation emails to the same address
    """

    __tablename__ = "sent_confirmation_mails"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
