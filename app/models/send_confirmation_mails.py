from datetime import UTC, datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db


class SentConfirmationMails(db.Model):
    """
    This model exists so that we can avoid sending too many
    confirmation emails to the same address (per-target) and from the same
    account (per-originator), preventing confirmation-mail bombing.
    """

    __tablename__ = "sent_confirmation_mails"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(120))
    # Originating account. Nullable so historic rows (pre-migration) remain valid.
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC)
    )
