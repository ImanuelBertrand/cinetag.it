from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class MiscData(db.Model):
    __tablename__ = "misc_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(50), unique=True)
    value: Mapped[str] = mapped_column(String(255))

    @staticmethod
    def save(key, value, commit=False) -> None:
        data = MiscData.query.filter_by(key=key).first()
        if data:
            data.value = value
        else:
            data = MiscData(key=key, value=value)
        db.session.add(data)
        if commit:
            db.session.commit()

    @staticmethod
    def get(key, default: str | None = None) -> str | None:
        data = MiscData.query.filter_by(key=key).first()
        return data.value if data else default

    def __repr__(self) -> str:
        return f"<MiscData {self.key}: {self.value}>"
