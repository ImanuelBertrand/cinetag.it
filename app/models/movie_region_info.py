from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.movie import Movie


class MovieRegionInfo(db.Model):
    __tablename__ = "movie_region_info"

    id: Mapped[int] = mapped_column(primary_key=True)
    movie_id: Mapped[int] = mapped_column(ForeignKey("movies.id"))
    region: Mapped[str] = mapped_column(String(2))
    release_date: Mapped[datetime.date] = mapped_column(Date)
    is_fake: Mapped[bool | None] = mapped_column(default=False)

    movie: Mapped[Movie] = relationship(back_populates="region_infos")

    __table_args__ = (
        UniqueConstraint("movie_id", "region", name="movie_region_info_idx"),
        Index("movie_region_info_release_date_idx", "release_date"),
    )

    def __repr__(self) -> str:
        return f"<MovieRegionInfo {self.movie_id} ({self.region})>"

    @staticmethod
    def create_from_tmdb(movie_id: int, region: str, date) -> MovieRegionInfo:
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
