from typing import Any

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class TmdbRegion(db.Model):
    __tablename__ = "tmdb_regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True)
    english_name: Mapped[str] = mapped_column(String(50))
    native_name: Mapped[str] = mapped_column(String(50))
    sort_order: Mapped[int] = mapped_column(default=0)

    def get_name(self) -> str:
        return self.native_name or self.english_name

    @staticmethod
    def create_from_tmdb(data: dict) -> TmdbRegion:
        return TmdbRegion(
            code=data["iso_3166_1"],
            english_name=data["english_name"],
            native_name=data["native_name"],
        )

    def update_from_tmdb(self, data) -> bool:
        updated = False
        if self.english_name != data["english_name"]:
            self.english_name = data["english_name"]
            updated = True
        if self.native_name != data["native_name"]:
            self.native_name = data["native_name"]
            updated = True
        return updated

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "english_name": self.english_name,
            "native_name": self.native_name,
            "sort_order": self.sort_order,
        }
