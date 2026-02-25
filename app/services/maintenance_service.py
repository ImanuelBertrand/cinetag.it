from datetime import UTC, datetime, timedelta

from sqlalchemy import exists

from app.extensions import db
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.models.user import User
from app.models.user_calendar import UserCalendar
from app.models.user_movie import UserMovie


def purge_abandoned_guests(retention_days: int = 14, dry_run: bool = True) -> dict:
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

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

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


def purge_inactive_empty_guests_with_tokens(
    retention_days: int = 14, dry_run: bool = True
) -> dict:
    """
    Delete guest users who STILL have at least one allowed refresh token but have
    no user_movies and no calendars, and are older than the retention window.

    Safeguards:
    - Only pure guests (email IS NULL, password IS NULL, new_email IS NULL)
    - Must have at least one allowed refresh token
    - Must have no user data (no movies, no calendars)
    - Must be older than cutoff (created_at & updated_at < cutoff)

    Returns a result dict. If dry_run=True, only reports candidates.
    """

    cutoff = datetime.now(UTC) - timedelta(days=retention_days)

    has_any_movie = exists().where(UserMovie.user_id == User.id)
    has_any_calendar = exists().where(UserCalendar.user_id == User.id)

    q = (
        User.query.filter(User.email.is_(None))
        .filter(User.password.is_(None))
        .filter(User.new_email.is_(None))
        .filter(User.created_at < cutoff)
        .filter(User.updated_at < cutoff)
        .filter(~has_any_movie)  # no user movies
        .filter(~has_any_calendar)  # no calendars
    )

    candidates = q.all()
    count = len(candidates)

    if dry_run:
        return {"to_delete": count, "ids": [u.id for u in candidates]}

    for u in candidates:
        db.session.delete(u)
    db.session.commit()

    return {"deleted": count}
