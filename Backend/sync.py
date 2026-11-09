"""Coordinate manual and scheduled imports with durable, secret-free status."""

from dataclasses import dataclass
from datetime import datetime, timezone
import logging
from threading import Lock
from urllib.error import URLError

from requests.exceptions import RequestException

from .models import ItemSource, SourceSyncState

logger = logging.getLogger(__name__)

SOURCES = (ItemSource.GOOGLE_CAL, ItemSource.GOOGLE_TASKS, ItemSource.LMS, ItemSource.CAMO, ItemSource.OUTLOOK)
LABELS = {"google_cal": "Google Calendar", "google_tasks": "Google Tasks", "lms": "Bennett LMS", "camo": "MyCamu", "outlook": "Outlook"}


@dataclass(frozen=True)
class SourceConfiguration:
    ready: bool
    mode: str
    revision: str = ""
    detail: str = ""


class SyncError(RuntimeError):
    def __init__(self, message, status_code=502):
        super().__init__(message)
        self.status_code = status_code


def utc_iso(value):
    if value is None:
        return None
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()


def log_unexpected_failure(source, error, operation="refreshing"):
    # Preserve traceback frames/type, not provider response bodies, exception
    # chains or frame locals that can include authentication secrets.
    safe_error = RuntimeError("Exception details omitted to protect connection secrets.")
    logger.exception("Unexpected failure %s %s (%s)", operation, source.value, type(error).__name__,
                     exc_info=(type(error), safe_error, error.__traceback__))


def failure_details(source, error):
    statuses = (getattr(error, "status_code", None), getattr(getattr(error, "response", None), "status_code", None),
                getattr(getattr(error, "resp", None), "status", None), getattr(error, "code", None))
    status = next((value for value in statuses if isinstance(value, int) and 400 <= value <= 599), None)
    label = LABELS[source.value]
    if status in (401, 403, 409):
        return "needs_sign_in", f"Reconnect {label} in Profile to continue automatic syncing.", 409
    if status is not None or isinstance(error, (RequestException, URLError, ConnectionError, TimeoutError)):
        if status is not None and status < 500 and status not in (408, 425, 429):
            return "error", f"{label} could not refresh. Check its connection settings.", status
        return "error", f"{label} could not refresh. It will retry on the next cycle.", 502
    log_unexpected_failure(source, error)
    return "error", f"{label} encountered an internal sync error. Report this issue if it persists.", 500


class SyncCoordinator:
    def __init__(self, session_factory, perform, configuration):
        self.session_factory = session_factory
        self.perform = perform
        self.configuration = configuration
        self.lock = Lock()
        self.active_source = None

    def initialize(self):
        """Seed or recover state explicitly after application schema setup."""
        with self.lock:
            with self.session_factory() as db:
                for source in SOURCES:
                    state = db.get(SourceSyncState, source.value)
                    if state is None:
                        db.add(SourceSyncState(source=source.value))
                    elif state.state == "running":
                        state.state = "interrupted"
                        state.last_error = "The previous refresh was interrupted; it will retry."
                db.commit()

    def _failure(self, source, error, revision=""):
        state_name, message, status = failure_details(source, error)
        logger.warning("daymark.sync.failed", extra={"event": "daymark.sync.failed", "source": source.value,
                       "failure_kind": state_name, "status_code": status})
        try:
            with self.session_factory() as metadata:
                state = metadata.get(SourceSyncState, source.value)
                state.state = state_name
                state.last_finished_at = datetime.now(timezone.utc)
                state.last_error = message
                state.config_revision = revision
                metadata.commit()
        except Exception as metadata_error:
            log_unexpected_failure(source, metadata_error, "recording failure for")
        return SyncError(message, status)

    def _run(self, source, db, config):
        self.active_source = source.value
        started = datetime.now(timezone.utc)
        try:
            with self.session_factory() as metadata:
                state = metadata.get(SourceSyncState, source.value)
                state.state = "running"
                state.last_started_at = started
                state.last_error = None
                metadata.commit()
            result = self.perform(source, db)
            result = result.model_dump() if hasattr(result, "model_dump") else result
            for key in ("imported", "updated"):
                if not isinstance(result[key], int) or isinstance(result[key], bool) or result[key] < 0:
                    raise ValueError("Sync result counts must be non-negative integers.")
            latest_config = self.configuration(source)
            with self.session_factory() as metadata:
                state = metadata.get(SourceSyncState, source.value)
                state.state = "success"
                state.last_finished_at = state.last_success_at = datetime.now(timezone.utc)
                state.last_error = None
                state.config_revision = latest_config.revision
                state.imported, state.updated = result["imported"], result["updated"]
                metadata.commit()
            return result
        except Exception as error:
            try:
                db.rollback()
            except Exception as rollback_error:
                log_unexpected_failure(source, rollback_error, "rolling back")
            raise self._failure(source, error, config.revision) from None
        finally:
            self.active_source = None

    def run_one(self, source, db):
        if source not in SOURCES:
            raise SyncError("Manual items cannot be synced.", 400)
        if not self.lock.acquire(blocking=False):
            raise SyncError("A refresh is already running. Wait for it to finish.", 409)
        try:
            config = self.configuration(source)
            if not config.ready:
                raise SyncError(f"Connect {LABELS[source.value]} in Profile before syncing.", 409)
            return self._run(source, db, config)
        except SyncError:
            raise
        except Exception as error:
            raise self._failure(source, error) from None
        finally:
            self.lock.release()

    def run_all(self, automatic=False):
        if not self.lock.acquire(blocking=False):
            return {"results": [], "errors": [], "skipped": [], "busy": True}
        results, errors, skipped = [], [], []
        try:
            for source in SOURCES:
                try:
                    config = self.configuration(source)
                    with self.session_factory() as metadata:
                        state = metadata.get(SourceSyncState, source.value)
                        if not config.ready:
                            if state.state != "needs_sign_in":
                                state.state = "not_connected"
                            metadata.commit()
                            skipped.append({"source": source.value, "reason": "not_connected"})
                            continue
                        if automatic and state.state == "needs_sign_in" and state.config_revision == config.revision:
                            skipped.append({"source": source.value, "reason": "needs_sign_in"})
                            continue
                        if automatic and config.mode == "snapshot" and state.state == "success" and state.config_revision == config.revision:
                            skipped.append({"source": source.value, "reason": "snapshot_unchanged"})
                            continue
                    # Each provider gets its own transaction; a failure cannot
                    # leave the next provider using a rolled-back/dirty session.
                    with self.session_factory() as db:
                        results.append(self._run(source, db, config))
                except SyncError as error:
                    errors.append(str(error))
                except Exception as error:
                    errors.append(str(self._failure(source, error)))
            return {"results": results, "errors": errors, "skipped": skipped, "busy": False}
        finally:
            self.active_source = None
            self.lock.release()

    def status(self):
        result = []
        with self.session_factory() as db:
            for source in SOURCES:
                config = self.configuration(source)
                state = db.get(SourceSyncState, source.value)
                result.append({"source": source.value, "label": LABELS[source.value], "ready": config.ready, "mode": config.mode, "detail": config.detail,
                               "state": state.state, "last_started_at": utc_iso(state.last_started_at), "last_finished_at": utc_iso(state.last_finished_at), "last_success_at": utc_iso(state.last_success_at), "error": state.last_error, "imported": state.imported, "updated": state.updated})
        return {"running": self.lock.locked(), "active_source": self.active_source, "sources": result}
