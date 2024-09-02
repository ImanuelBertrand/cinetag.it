from app.extensions import db


class MiscData(db.Model):
    __tablename__ = "misc_data"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), nullable=False, unique=True)
    value = db.Column(db.String(255), nullable=False)

    @staticmethod
    def save(key, value, commit=False):
        data = MiscData.query.filter_by(key=key).first()
        if data:
            data.value = value
        else:
            data = MiscData(key=key, value=value)
        db.session.add(data)
        if commit:
            db.session.commit()

    @staticmethod
    def get(key, default: str = None) -> str:
        data = MiscData.query.filter_by(key=key).first()
        return data.value if data else default

    def __repr__(self):
        return f"<MiscData {self.key}: {self.value}>"
