from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, backref, mapped_column, relationship

from app.extensions import db

_logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.models.user import User


class AllowedRefreshToken(db.Model):
    """
    Stores JTIs of refresh tokens that are currently allowed.
    Acts as an 'allowlist'. Revocation involves deleting the entry.
    """

    __tablename__ = "allowed_refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)

    # JTI (JWT ID) claim, usually a UUID string. Indexed for fast lookups.
    jti: Mapped[str] = mapped_column(String(36), unique=True, index=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
    )

    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
    )

    user: Mapped[User] = relationship(
        backref=backref(
            "allowed_refresh_tokens", lazy=True, cascade="all, delete-orphan"
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AllowedRefreshToken jti={self.jti} "
            f"user_id={self.user_id} expires_at={self.expires_at}>"
        )

    @staticmethod
    def is_token_allowed(jti: str, user_id: int) -> bool:
        """
        Checks if a token with the given JTI exists in the allowlist.
        Does NOT check expiry here, assumes expired tokens are cleaned up.
        """
        return (
            db.session.query(AllowedRefreshToken.id)
            .filter_by(jti=jti, user_id=user_id)
            .scalar()
            is not None
        )

    @staticmethod
    def add_token(jti: str, user_id: int, expires_at_timestamp: float) -> None:
        """Adds a new token JTI to the allowlist."""
        if not jti or not user_id or not expires_at_timestamp:
            _logger.error(
                "Attempted to add token with missing jti, user_id, or expires_at."
            )
            return

        # Convert UNIX timestamp to timezone-aware datetime
        expires_dt = datetime.fromtimestamp(expires_at_timestamp, tz=UTC)

        new_token = AllowedRefreshToken(jti=jti, user_id=user_id, expires_at=expires_dt)
        db.session.add(new_token)
        _logger.debug("Added refresh token %s for user %s to allowlist.", jti, user_id)
        # Note: Commit should happen as part
        # of the transaction where the token is issued.

    @staticmethod
    def revoke_token(jti: str) -> bool:
        """Removes a token JTI from the allowlist (revokes it)."""
        token_entry = AllowedRefreshToken.query.filter_by(jti=jti).first()
        if token_entry:
            db.session.delete(token_entry)
            _logger.debug(
                "Revoked refresh token %s for user %s.", jti, token_entry.user_id
            )
            return True
        return False

    @staticmethod
    def revoke_all_for_user(user_id: int) -> bool:
        """Revokes all refresh tokens for a specific user."""
        deleted_count = AllowedRefreshToken.query.filter_by(user_id=user_id).delete()
        _logger.info("Revoked %s refresh token(s) for user %s.", deleted_count, user_id)
        # Note: Commit should happen as part
        # of the transaction (e.g., password change).
        return deleted_count > 0

    @staticmethod
    def cleanup_expired_tokens() -> int:
        """Deletes expired token entries from the database.
        Should be run periodically."""
        now = datetime.now(UTC)
        try:
            expired_count = AllowedRefreshToken.query.filter(
                AllowedRefreshToken.expires_at < now
            ).delete()
            db.session.commit()  # Commit the cleanup transaction immediately
        except Exception:
            _logger.exception("Error during expired refresh token cleanup")
            db.session.rollback()
            return 0
        else:
            if expired_count > 0:
                _logger.info(
                    "Cleaned up %s expired refresh token entries.", expired_count
                )
            return expired_count
