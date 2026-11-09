from datetime import datetime, timedelta, timezone

from apscheduler.executors.pool import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler


def create_scheduler(callback, interval_seconds=300) -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="UTC", executors={"default": ThreadPoolExecutor(max_workers=1)})
    scheduler.add_job(callback, "interval", seconds=interval_seconds, id="source_sync", max_instances=1, coalesce=True, misfire_grace_time=60, next_run_time=datetime.now(timezone.utc) + timedelta(seconds=1))
    return scheduler
