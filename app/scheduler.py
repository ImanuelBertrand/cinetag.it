import atexit
import logging
from datetime import UTC, datetime
from functools import partial

from app.extensions import scheduler
from app.models.allowed_refresh_token import AllowedRefreshToken
from app.services.maintenance_service import purge_abandoned_guests
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


def shutdown_scheduler_if_running():
    if scheduler.running:
        scheduler.shutdown()
        _logger.info("Scheduler shut down successfully")
    else:
        _logger.info("Scheduler is not running")


atexit.register(shutdown_scheduler_if_running)


def run_with_context(func):
    with scheduler.app.app_context():
        func()


def job_cleanup_expired_refresh_tokens():
    # Best-effort; no exception should crash scheduler
    try:
        AllowedRefreshToken.cleanup_expired_tokens()
    except Exception:
        _logger.exception("Error cleaning expired tokens")


def job_purge_abandoned_guests():
    try:
        # Allow configuration override;
        # default 21 days to be safer than refresh lifetime
        days = scheduler.app.config.get("GUEST_RETENTION_DAYS", 21)
        purge_abandoned_guests(retention_days=days, dry_run=False)
    except Exception:
        _logger.exception("Error purging abandoned guests")


def job_purge_empty_guests():
    try:
        # Separate retention window for empty guests that still have tokens
        days = scheduler.app.config.get("GUEST_EMPTY_RETENTION_DAYS", 21)
        # import locally to avoid expanding top-level imports
        from app.services.maintenance_service import (
            purge_inactive_empty_guests_with_tokens,
        )

        purge_inactive_empty_guests_with_tokens(retention_days=days, dry_run=False)
    except Exception:
        _logger.exception("Error purging empty guests")


def setup_cron_jobs():
    # Check if scheduler is enabled in config
    if (
        hasattr(scheduler.app, "config")
        and scheduler.app.config.get("SCHEDULER_ENABLED", True) is False
    ):
        _logger.info("Scheduler is disabled in config, skipping cron job setup")
        return

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
            **job_definition["options"],
        )

    # Only start the scheduler if it's not already running
    if not scheduler.running:
        scheduler.start()
