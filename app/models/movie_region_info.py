from datetime import datetime

from app.extensions import db


class MovieRegionInfo(db.Model):
    __tablename__ = "movie_region_info"

    id = db.Column(db.Integer, primary_key=True)
    movie_id = db.Column(db.Integer, db.ForeignKey("movies.id"), nullable=False)
    region = db.Column(db.String(2), nullable=False)
    release_date = db.Column(db.Date, nullable=False)
    is_fake = db.Column(db.Boolean, default=False)

    movie = db.relationship("Movie", back_populates="region_infos")

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
        if self.is_fake:
            self.is_fake = False
            updated = True
        return updated
