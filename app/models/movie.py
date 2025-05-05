from typing import Dict

from app.extensions import db
from app.models.movie_language_info import MovieLanguageInfo


class Movie(db.Model):
    __tablename__ = "movies"

    id = db.Column(db.Integer, primary_key=True)
    original_title = db.Column(db.String(255), nullable=False)
    popularity = db.Column(db.Float, nullable=True)
    original_language = db.Column(db.String(2), nullable=True)
    info_update_at = db.Column(db.DateTime, nullable=True)
    imdb_id = db.Column(db.String(20), nullable=True)
    origin_country = db.Column(db.String(255), nullable=True)
    runtime = db.Column(db.Integer, nullable=True)
    spoken_languages = db.Column(db.String(255), nullable=True)

    region_infos = db.relationship(
        "MovieRegionInfo", back_populates="movie", cascade="all, delete-orphan"
    )
    language_infos = db.relationship(
        "MovieLanguageInfo", back_populates="movie", cascade="all, delete-orphan"
    )

    user_movies = db.relationship(
        "UserMovie", back_populates="movie", cascade="all, delete-orphan"
    )

    notifications = db.relationship(
        "Notification", back_populates="movie", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Movie {self.id} ({self.original_title})>"

    def get_localized_data(
        self, lang: str, language_infos: "Dict[str, MovieLanguageInfo]" = None
    ) -> Dict[str, str]:
        if language_infos is None:
            language_infos = {
                lang_info.language: lang_info for lang_info in self.language_infos
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

        if "origin_country" in data:
            origin_country = ",".join(data.get("origin_country", []))
            if self.origin_country != origin_country:
                self.origin_country = origin_country
                updated = True

        if "spoken_languages" in data:
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
