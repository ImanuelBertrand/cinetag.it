from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from datetime import datetime

    from app.models.movie import Movie


class TmdbGenre(db.Model):
    __tablename__ = "tmdb_genres"

    # Use TMDb's stable genre id as the primary key
    id: Mapped[int] = mapped_column(primary_key=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationship for localized names
    names: Mapped[list[TmdbGenreName]] = relationship(
        back_populates="genre", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<TmdbGenre {self.id}>"


class TmdbGenreName(db.Model):
    __tablename__ = "tmdb_genre_names"

    genre_id: Mapped[int] = mapped_column(
        ForeignKey("tmdb_genres.id"), primary_key=True
    )
    language: Mapped[str] = mapped_column(String(8), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    genre: Mapped[TmdbGenre] = relationship(back_populates="names")

    def __repr__(self) -> str:
        return f"<TmdbGenreName {self.genre_id}:{self.language}={self.name}>"


class MovieGenre(db.Model):
    __tablename__ = "movie_genres"

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True
    )
    genre_id: Mapped[int] = mapped_column(
        ForeignKey("tmdb_genres.id"), primary_key=True
    )

    movie: Mapped[Movie] = relationship(back_populates="genres")

    def __repr__(self) -> str:
        return f"<MovieGenre {self.movie_id}:{self.genre_id}>"
