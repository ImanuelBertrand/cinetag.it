import atexit
import fcntl
import logging
import os
from datetime import UTC, datetime
from functools import partial
from typing import Any, cast

from app.extensions import scheduler
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.services.backup_service import run_backup_if_due
from app.services.maintenance_service import (
    purge_abandoned_guests,
    purge_inactive_empty_guests_with_tokens,
)
from app.services.tmdb_service import (
    refresh_changed_movies,
    refresh_outdated_movies,
    update_all_upcoming_movies,
    update_languages,
    update_regions,
)
from app.utils.email import send_queued_emails
from app.utils.notifications import (
    cron_send_notifications,
    cron_setup_notifications,
)

_logger = logging.getLogger(__name__)

# Holds the lock fd for the process lifetime so the kernel-level flock stays
# held until the process exits. Module-global so setup_cron_jobs is idempotent
# within a single worker.
_scheduler_lock_fd: int | None = None


def _acquire_scheduler_lock(instance_path: str) -> bool:
    """Acquire an exclusive lock so only one worker per container runs cron jobs.

    Uses fcntl.flock on a lockfile in the instance dir. The fd is intentionally
    leaked for the lifetime of the process; the kernel releases the lock on
    process exit, so a worker restart hands the lock to whichever sibling
    re-enters this function first.
    """
    global _scheduler_lock_fd
    if _scheduler_lock_fd is not None:
        return True

    os.makedirs(instance_path, exist_ok=True)
    lock_path = os.path.join(instance_path, "scheduler.lock")
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return False
    _scheduler_lock_fd = fd
    return True


def shutdown_scheduler_if_running() -> None:
    if scheduler.running:
        scheduler.shutdown()
        _logger.debug("Scheduler shut down successfully")
    else:
        _logger.debug("Scheduler is not running")


atexit.register(shutdown_scheduler_if_running)


def run_with_context(func) -> None:
    app = scheduler.app
    if app is None:
        raise RuntimeError("Scheduler app is not initialized")
    with app.app_context():
        func()


def job_cleanup_expired_refresh_tokens() -> None:
    # Best-effort; no exception should crash scheduler
    try:
        AllowedRefreshToken.cleanup_expired_tokens()
    except Exception:
        _logger.exception("Error cleaning expired tokens")


def job_purge_abandoned_guests() -> None:
    try:
        # Allow configuration override;
        # default 21 days to be safer than refresh lifetime
        app = scheduler.app
        if app is None:
            return
        days = app.config.get("GUEST_RETENTION_DAYS", 21)
        purge_abandoned_guests(retention_days=days, dry_run=False)
    except Exception:
        _logger.exception("Error purging abandoned guests")


def job_run_backup() -> None:
    try:
        run_backup_if_due()
    except Exception:
        _logger.exception("Error running scheduled DB backup")


def job_purge_empty_guests() -> None:
    try:
        # Separate retention window for empty guests that still have tokens
        app = scheduler.app
        if app is None:
            return
        days = app.config.get("GUEST_EMPTY_RETENTION_DAYS", 21)
        # import locally to avoid expanding top-level imports

        purge_inactive_empty_guests_with_tokens(retention_days=days, dry_run=False)
    except Exception:
        _logger.exception("Error purging empty guests")


def setup_cron_jobs() -> None:
    # Check if scheduler is enabled in config
    if (
        hasattr(scheduler.app, "config")
        and scheduler.app.config.get("SCHEDULER_ENABLED", True) is False
    ):
        _logger.info("Scheduler is disabled in config, skipping cron job setup")
        return

    app = scheduler.app
    if app is None:
        _logger.warning("Scheduler has no app attached; skipping cron job setup")
        return

    if not _acquire_scheduler_lock(app.instance_path):
        _logger.info(
            "Scheduler lock held by another worker (pid %s); "
            "skipping cron job setup in this process",
            os.getpid(),
        )
        return

    _logger.info("Acquired scheduler lock in pid %s", os.getpid())

    job_definitions = {
        "update_regions": {
            "func": update_regions,
            "options": {"hours": 24},
        },
        "update_languages": {
            "func": update_languages,
            "options": {"hours": 24},
        },
        "update_all_upcoming_movies": {
            "func": update_all_upcoming_movies,
            "options": {"hours": 1},
        },
        "send_email_queue": {
            "func": send_queued_emails,
            "options": {"seconds": 15, "executor": "concurrent"},
        },
        "refresh_outdated_movies": {
            "func": refresh_outdated_movies,
            "options": {"minutes": 15},
        },
        "refresh_changed_movies": {
            "func": refresh_changed_movies,
            "options": {"hours": 1},
        },
        "send_notifications": {
            "func": cron_send_notifications,
            "options": {"hours": 1},
        },
        "setup_notifications": {
            "func": cron_setup_notifications,
            "options": {"hours": 1},
        },
        "cleanup_expired_refresh_tokens": {
            "func": job_cleanup_expired_refresh_tokens,
            "options": {"hours": 24},
        },
        "purge_abandoned_guests": {
            "func": job_purge_abandoned_guests,
            "options": {"hours": 24},
        },
        "purge_empty_guests_with_tokens": {
            "func": job_purge_empty_guests,
            "options": {"hours": 24},
        },
        "run_db_backup": {
            "func": job_run_backup,
            "options": {"hours": 1},
        },
    }
    for job_id, job_definition in job_definitions.items():
        scheduler.add_job(
            id=job_id,
            trigger="interval",
            next_run_time=datetime.now(UTC),
            misfire_grace_time=7200,
            max_instances=1,
            coalesce=True,
            func=partial(run_with_context, job_definition["func"]),
            **cast("dict[str, Any]", job_definition["options"]),
        )

    # Only start the scheduler if it's not already running
    if not scheduler.running:
        scheduler.start()
