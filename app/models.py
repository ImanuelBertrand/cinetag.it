from datetime import datetime

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
    popularity = db.Column(db.Float, nullable=True)
    original_language = db.Column(db.String(2), nullable=True)
    info_update_at = db.Column(db.DateTime, nullable=True)

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
        return updated

    @staticmethod
    def create_from_tmdb(data: dict) -> "Movie":
        return Movie(
            id=data["id"],
            original_title=data["original_title"],
            popularity=data["popularity"],
            original_language=data["original_language"],
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
