import atexit
import logging
from datetime import datetime
from functools import partial

from app.extensions import scheduler
from app.services.tmdb_service import (
    update_regions,
    update_languages,
    update_all_upcoming_movies,
    refresh_outdated_movies,
    refresh_changed_movies,
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
    }
    for job_id, job_definition in job_definitions.items():
        scheduler.add_job(
            id=job_id,
            trigger="interval",
            next_run_time=datetime.now(),
            misfire_grace_time=7200,
            max_instances=1,
            coalesce=True,
            func=partial(run_with_context, job_definition["func"]),
            **job_definition["options"],
        )

    # Only start the scheduler if it's not already running
    if not scheduler.running:
        scheduler.start()
