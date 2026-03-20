from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class UserEmailQueue(db.Model):
    # Table to store pending emails for async email confirmation / PW reset
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    mail_type: Mapped[str] = mapped_column(String(10))

    user: Mapped[User] = relationship(backref="pending_emails")
