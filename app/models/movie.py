from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from datetime import datetime

    from app.models.movie_language_info import MovieLanguageInfo
    from app.models.movie_region_info import MovieRegionInfo
    from app.models.notification import Notification
    from app.models.tmdb_genre import MovieGenre
    from app.models.user_movie import UserMovie


class Movie(db.Model):
    __tablename__ = "movies"

    id: Mapped[int] = mapped_column(primary_key=True)
    original_title: Mapped[str] = mapped_column(String(255))
    popularity: Mapped[float | None] = mapped_column(Float)
    original_language: Mapped[str | None] = mapped_column(String(2))
    info_update_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imdb_id: Mapped[str | None] = mapped_column(String(20))
    origin_country: Mapped[str | None] = mapped_column(String(255))
    runtime: Mapped[int | None] = mapped_column()
    spoken_languages: Mapped[str | None] = mapped_column(String(255))

    region_infos: Mapped[list[MovieRegionInfo]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )
    language_infos: Mapped[list[MovieLanguageInfo]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )

    user_movies: Mapped[list[UserMovie]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )

    notifications: Mapped[list[Notification]] = relationship(
        back_populates="movie", cascade="all, delete-orphan"
    )

    genres: Mapped[list[MovieGenre]] = relationship(cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Movie {self.id} ({self.original_title})>"

    def get_localized_data(
        self, lang: str, language_infos: dict[str, MovieLanguageInfo] | None = None
    ) -> dict[str, str]:
        if language_infos is None:
            language_infos = {
                lang_info.language: lang_info
                for lang_info in self.language_infos  # type: ignore[not-iterable]
            }

        langs = [lang, "en", self.original_language]
        info_sources = [language_infos.get(key) for key in langs]
        fields = ["title", "overview", "tagline", "runtime", "poster_path"]
        fallbacks = {"title": self.original_title, "runtime": self.runtime}

        return {
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
    def create_from_tmdb(data: dict) -> Movie:
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
