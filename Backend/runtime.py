"""Single-process ownership, operational logging and local readiness probes."""

from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import traceback

from sqlalchemy import text
from sqlalchemy.engine import make_url


class JsonFormatter(logging.Formatter):
    def format(self, record):
        result = {"time": datetime.now(timezone.utc).isoformat(), "level": record.levelname,
                  "logger": record.name, "message": record.getMessage()}
        for name in ("request_id", "method", "route", "status", "duration_ms", "event", "source", "failure_kind", "status_code", "executable"):
            if hasattr(record, name):
                result[name] = getattr(record, name)
        if record.exc_info:
            # Frame locations and exception type are useful; exception messages,
            # chained exceptions and locals may contain provider credentials.
            kind, _, frames = record.exc_info
            result["exception_type"] = kind.__name__
            result["traceback"] = [{"file": Path(frame.filename).name, "line": frame.lineno,
                                    "function": frame.name} for frame in traceback.extract_tb(frames)]
        return json.dumps(result)


def configure_logging():
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=logging.INFO, handlers=[handler], force=True)
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


@contextmanager
def single_worker(url):
    """Hold an OS lock for this database until the scheduler has stopped.

    OS locks are released after a crash. Leave the empty lock file in place to
    avoid inode replacement races between overlapping POSIX processes.
    """
    address = make_url(url)
    identity = str(address)
    if address.get_backend_name() == "sqlite" and address.database not in (None, "", ":memory:"):
        identity = str(Path(address.database).resolve()).casefold()
    key = hashlib.sha256(identity.encode()).hexdigest()
    path = Path(tempfile.gettempdir()) / f"daymark-worker-{key}.lock"
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise RuntimeError("Daymark is already running for this database. Use one backend worker.") from None
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def readiness(engine, scheduler, enabled):
    database_ok = False
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1 FROM items LIMIT 1"))
        database_ok = True
    except Exception:
        logging.getLogger(__name__).exception("Database readiness probe failed")
    scheduler_ok = not enabled or bool(scheduler and scheduler.running and scheduler.get_job("source_sync"))
    return {"status": "ok" if database_ok and scheduler_ok else "unavailable",
            "database": "ok" if database_ok else "unavailable",
            "scheduler": "disabled" if not enabled else "running" if scheduler_ok else "unavailable"}
