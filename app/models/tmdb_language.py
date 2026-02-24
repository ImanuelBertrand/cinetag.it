from app.extensions import db


class TmdbLanguage(db.Model):
    __tablename__ = "tmdb_languages"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(2), nullable=False, unique=True)
    english_name = db.Column(db.String(50), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    sort_order = db.Column(db.Integer, nullable=False, default=0)

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
