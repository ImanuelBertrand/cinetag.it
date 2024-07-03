import atexit
import logging
from datetime import datetime
from functools import partial

from app.extensions import scheduler
from app.services.tmdb_service import (
    update_regions,
    update_languages,
)

_logger = logging.getLogger(__name__)
atexit.register(scheduler.shutdown)


def run_with_context(func):
    with scheduler.app.app_context():
        func()


def setup_cron_jobs():
    job_definitions = {
        "update_regions": {"func": update_regions, "hours": 24},
        "update_languages": {"func": update_languages, "hours": 24},
    }
    for job_id, job_definition in job_definitions.items():
        scheduler.add_job(
            id=job_id,
            trigger="interval",
            next_run_time=datetime.now(),
            misfire_grace_time=60,
            coalesce=True,
            func=partial(run_with_context, job_definition["func"]),
            hours=job_definition["hours"],
        )

    scheduler.start()
