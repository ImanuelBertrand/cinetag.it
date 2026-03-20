from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class TmdbLanguage(db.Model):
    __tablename__ = "tmdb_languages"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True)
    english_name: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(default=0)

    def get_name(self) -> str:
        return self.name or self.english_name

    @staticmethod
    def create_from_tmdb(data: dict) -> TmdbLanguage:
        return TmdbLanguage(
            code=data["iso_639_1"],
            english_name=data["english_name"],
            name=data["name"] if data["name"] and data["name"].replace("?", "") else "",
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        if self.english_name != data["english_name"]:
            self.english_name = data["english_name"]
            updated = True
        name = data["name"] if data["name"] and data["name"].replace("?", "") else ""
        if self.name != name:
            self.name = name
            updated = True
        return updated
