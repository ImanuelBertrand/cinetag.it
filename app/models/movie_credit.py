from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.movie import Movie


class Person(db.Model):
    __tablename__ = "people"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(255))

    def __repr__(self) -> str:
        return f"<Person {self.id} ({self.name})>"


class MovieCredit(db.Model):
    __tablename__ = "movie_credits"

    movie_id: Mapped[int] = mapped_column(
        ForeignKey("movies.id", ondelete="CASCADE"), primary_key=True
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("people.id", ondelete="CASCADE"), primary_key=True
    )
    # "cast" or "crew"
    department: Mapped[str] = mapped_column(String(8), primary_key=True)
    # Cast: character name. Crew: job (e.g. "Director", "Screenplay").
    role: Mapped[str] = mapped_column(String(255), primary_key=True)
    # Cast: TMDB billing order. Crew: 0.
    sort_order: Mapped[int] = mapped_column(default=0)

    movie: Mapped[Movie] = relationship(back_populates="credits")
    person: Mapped[Person] = relationship()

    __table_args__ = (Index("ix_movie_credits_movie_dept", "movie_id", "department"),)

    def __repr__(self) -> str:
        return (
            f"<MovieCredit {self.movie_id}:{self.person_id} "
            f"{self.department}/{self.role}>"
        )
