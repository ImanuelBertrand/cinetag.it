from typing import Dict, Any

from app.extensions import db


class TmdbRegion(db.Model):
    __tablename__ = "tmdb_regions"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), nullable=False, unique=True)
    english_name = db.Column(db.String(50), nullable=False)
    native_name = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

    def get_name(self) -> str:
        return self.native_name or self.english_name

    @staticmethod
    def create_from_tmdb(data: dict) -> "TmdbRegion":
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

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "code": self.code,
            "english_name": self.english_name,
            "native_name": self.native_name,
            "sort_order": self.sort_order,
        }
