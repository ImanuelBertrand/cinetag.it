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

_logger = logging.getLogger(__name__)
atexit.register(scheduler.shutdown)


def run_with_context(func):
    with scheduler.app.app_context():
        func()


def setup_cron_jobs():
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

    scheduler.start()
