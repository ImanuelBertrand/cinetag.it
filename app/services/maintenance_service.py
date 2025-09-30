from datetime import datetime, timedelta
from typing import Dict

from sqlalchemy import exists

from app.extensions import db
from app.models.user import User
from app.models.allowed_refresh_token import AllowedRefreshToken


def purge_abandoned_guests(retention_days: int = 14, dry_run: bool = True) -> Dict:
    """
    Delete guest users (no email, no password, no new_email) who have no allowed
    refresh tokens and are older than the retention window.

    Returns a result dict. If dry_run=True, does not delete, only reports.
    """
    # Ensure expired token entries are gone so the allowlist reflects reality
    try:
        AllowedRefreshToken.cleanup_expired_tokens()
    except Exception:
        # Best-effort cleanup; proceed even if cleanup failed
        db.session.rollback()

    cutoff = datetime.utcnow() - timedelta(days=retention_days)

    # EXISTS subquery: does this user have any allowed refresh token?
    has_allowed_token = exists().where(AllowedRefreshToken.user_id == User.id)

    # Only pure guests (exclude users in the middle of registration)
    q = (
        User.query.filter(User.email.is_(None))
        .filter(User.password.is_(None))
        .filter(User.new_email.is_(None))
        .filter(User.created_at < cutoff)
        .filter(User.updated_at < cutoff)
        .filter(~has_allowed_token)
    )

    candidates = q.all()
    count = len(candidates)

    if dry_run:
        return {"to_delete": count, "ids": [u.id for u in candidates]}

    for u in candidates:
        db.session.delete(u)
    db.session.commit()

    return {"deleted": count}
