from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.movie import Movie
    from app.models.notification_channel import NotificationChannel
    from app.models.user import User


class Notification(db.Model):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"))
    channel_id: Mapped[int | None] = mapped_column(
        ForeignKey("notification_channels.id")
    )
    movie_id: Mapped[int | None] = mapped_column(ForeignKey("movies.id"))
    days_in_advance: Mapped[int] = mapped_column()
    is_sent: Mapped[bool | None] = mapped_column(Boolean, default=False)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
    )

    channel: Mapped[NotificationChannel] = relationship(back_populates="notifications")
    user: Mapped[User] = relationship(back_populates="notifications")
    movie: Mapped[Movie] = relationship(back_populates="notifications")

    def __init__(
        self, user_id, channel_id, movie_id, days_in_advance, scheduled_at
    ) -> None:
        self.user_id = user_id
        self.channel_id = channel_id
        self.movie_id = movie_id
        self.days_in_advance = days_in_advance
        self.scheduled_at = scheduled_at
