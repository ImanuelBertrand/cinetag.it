from datetime import datetime

from app.extensions import db


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=True)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password = db.Column(db.String(128), nullable=True)
    email_confirmed = db.Column(db.Boolean, default=False)
    region = db.Column(db.String(2), nullable=True, default="US")
    language = db.Column(db.String(5), nullable=True, default="en-US")
    is_temporary = db.Column(db.Boolean, default=True)
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

    region_info = db.relationship(
        "MovieRegionInfo", back_populates="movie", cascade="all, delete-orphan"
    )
    language_info = db.relationship(
        "MovieLanguageInfo", back_populates="movie", cascade="all, delete-orphan"
    )

    user_movies = db.relationship(
        "UserMovie", back_populates="movie", cascade="all, delete-orphan"
    )

    popularity = db.Column(db.Float, nullable=True)

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
            popularity=data["popularity"],
        )


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


class TmdbLanguage(db.Model):
    __tablename__ = "tmdb_languages"

    id = db.Column(db.Integer, primary_key=True)
    iso_639_1 = db.Column(db.String(2), nullable=False)
    english_name = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(50), nullable=False)

    @staticmethod
    def create_from_tmdb(data: dict) -> "TmdbLanguage":
        return TmdbLanguage(
            iso_639_1=data["iso_639_1"],
            english_name=data["english_name"],
            name=data["name"],
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        if self.english_name != data["english_name"]:
            self.english_name = data["english_name"]
            updated = True
        if self.name != data["name"]:
            self.name = data["name"]
            updated = True
        return updated


class TmdbRegion(db.Model):
    __tablename__ = "tmdb_regions"

    id = db.Column(db.Integer, primary_key=True)
    iso_3166_1 = db.Column(db.String(2), nullable=False)
    english_name = db.Column(db.String(50), nullable=False)
    native_name = db.Column(db.String(50), nullable=False)

    @staticmethod
    def create_from_tmdb(data: dict) -> "TmdbRegion":
        return TmdbRegion(
            iso_3166_1=data["iso_3166_1"],
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
