from app.extensions import db


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
