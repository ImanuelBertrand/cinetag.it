from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.movie import Movie


class MovieLanguageInfo(db.Model):
    __tablename__ = "movie_language_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"))
    language: Mapped[str] = mapped_column(String(5))
    title: Mapped[str] = mapped_column(String(255))
    poster_path: Mapped[str | None] = mapped_column(String(255))
    overview: Mapped[str | None] = mapped_column(Text)
    tagline: Mapped[str | None] = mapped_column(String(255))
    runtime: Mapped[int | None] = mapped_column()

    movie: Mapped[Movie] = relationship(back_populates="language_infos")

    __table_args__ = (
        UniqueConstraint("movie_id", "language", name="movie_language_info_idx"),
    )

    def __repr__(self) -> str:
        return f"<MovieLanguageInfo {self.movie_id} ({self.language})>"

    @staticmethod
    def create_from_tmdb(
        movie_id: int, data: dict, language: str | None = None
    ) -> MovieLanguageInfo:
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
