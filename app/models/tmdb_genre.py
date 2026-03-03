from app.extensions import db


class TmdbGenre(db.Model):
    __tablename__ = "tmdb_genres"

    # Use TMDb's stable genre id as the primary key
    id = db.Column(db.Integer, primary_key=True)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Relationship for localized names
    names = db.relationship(
        "TmdbGenreName", back_populates="genre", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TmdbGenre {self.id}>"


class TmdbGenreName(db.Model):
    __tablename__ = "tmdb_genre_names"

    genre_id = db.Column(db.Integer, db.ForeignKey("tmdb_genres.id"), primary_key=True)
    language = db.Column(db.String(8), primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), nullable=True)

    genre = db.relationship("TmdbGenre", back_populates="names")

    def __repr__(self) -> str:
        return f"<TmdbGenreName {self.genre_id}:{self.language}={self.name}>"


class MovieGenre(db.Model):
    __tablename__ = "movie_genres"

    movie_id = db.Column(
        db.Integer, db.ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id = db.Column(db.Integer, db.ForeignKey("tmdb_genres.id"), primary_key=True)

    movie = db.relationship("Movie", back_populates="genres")

    def __repr__(self) -> str:
        return f"<MovieGenre {self.movie_id}:{self.genre_id}>"
