import logging
from datetime import datetime, timezone

from app.extensions import db

_logger = logging.getLogger(__name__)


class AllowedRefreshToken(db.Model):
    """
    Stores JTIs of refresh tokens that are currently allowed.
    Acts as an 'allowlist'. Revocation involves deleting the entry.
    """

    __tablename__ = "allowed_refresh_tokens"

    id = db.Column(db.Integer, primary_key=True)

    # JTI (JWT ID) claim, usually a UUID string. Indexed for fast lookups.
    jti = db.Column(db.String(36), nullable=False, unique=True, index=True)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    user = db.relationship(
        "User",
        backref=db.backref(
            "allowed_refresh_tokens", lazy=True, cascade="all, delete-orphan"
        ),
    )

    def __repr__(self):
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
    def add_token(jti: str, user_id: int, expires_at_timestamp: float):
        """Adds a new token JTI to the allowlist."""
        if not jti or not user_id or not expires_at_timestamp:
            _logger.error(
                "Attempted to add token with missing jti, user_id, or expires_at."
            )
            return

        # Convert UNIX timestamp to timezone-aware datetime
        expires_dt = datetime.fromtimestamp(expires_at_timestamp, tz=timezone.utc)

        new_token = AllowedRefreshToken(jti=jti, user_id=user_id, expires_at=expires_dt)
        db.session.add(new_token)
        _logger.debug(f"Added refresh token {jti} for user {user_id} to allowlist.")
        # Note: Commit should happen as part
        # of the transaction where the token is issued.

    @staticmethod
    def revoke_token(jti: str):
        """Removes a token JTI from the allowlist (revokes it)."""
        token_entry = AllowedRefreshToken.query.filter_by(jti=jti).first()
        if token_entry:
            db.session.delete(token_entry)
            _logger.debug(
                f"Revoked refresh token {jti} for user {token_entry.user_id}."
            )
            return True
        return False

    @staticmethod
    def revoke_all_for_user(user_id: int):
        """Revokes all refresh tokens for a specific user."""
        deleted_count = AllowedRefreshToken.query.filter_by(user_id=user_id).delete()
        _logger.info(f"Revoked {deleted_count} refresh token(s) for user {user_id}.")
        # Note: Commit should happen as part
        # of the transaction (e.g., password change).
        return deleted_count > 0

    @staticmethod
    def cleanup_expired_tokens():
        """Deletes expired token entries from the database.
        Should be run periodically."""
        now = datetime.now(timezone.utc)
        try:
            expired_count = AllowedRefreshToken.query.filter(
                AllowedRefreshToken.expires_at < now
            ).delete()
            db.session.commit()  # Commit the cleanup transaction immediately

        except Exception as e:
            _logger.error(
                f"Error during expired refresh token cleanup: {e}", exc_info=True
            )
            db.session.rollback()
            return 0
        else:
            if expired_count > 0:
                _logger.info(
                    f"Cleaned up {expired_count} expired refresh token entries."
                )
            return expired_count
