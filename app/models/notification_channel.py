from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, Enum, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.notification import Notification
    from app.models.user import User


class NotificationChannel(db.Model):
    __tablename__ = "notification_channels"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    enabled: Mapped[bool | None] = mapped_column(Boolean)
    days_in_advance: Mapped[Any] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(
        Enum("email", "push", name="user_notification_mode")
    )
    notification_data: Mapped[Any | None] = mapped_column(JSON)
    include_maybe_movies: Mapped[bool | None] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship(back_populates="notification_channels")
    notifications: Mapped[list[Notification]] = relationship(
        back_populates="channel", cascade="all, delete-orphan"
    )

    @staticmethod
    def get_valid_types() -> list[str]:
        return ["email", "push"]

    def __init__(self, user_id: int, mode: str, enabled: bool) -> None:
        self.user_id = user_id
        self.mode = mode
        self.enabled = enabled
