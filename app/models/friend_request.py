from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.extensions import db

if TYPE_CHECKING:
    from app.models.user import User


class FriendRequest(db.Model):
    __tablename__ = "friend_requests"

    id: Mapped[int] = mapped_column(primary_key=True)
    requester_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    recipient_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(
        String(20), default="pending"
    )  # pending, accepted, rejected
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=datetime.now(UTC),
    )

    requester: Mapped[User] = relationship(
        foreign_keys=[requester_id],
        backref=backref("sent_friend_requests", lazy="dynamic"),
    )
    recipient: Mapped[User] = relationship(
        foreign_keys=[recipient_id],
        backref=backref("received_friend_requests", lazy="dynamic"),
    )

    __table_args__ = (
        Index("friend_request_idx", "requester_id", "recipient_id", unique=True),
    )
