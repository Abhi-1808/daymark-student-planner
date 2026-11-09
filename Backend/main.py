from contextlib import asynccontextmanager, nullcontext
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Annotated, Literal
from urllib.parse import quote, urlsplit

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .database import Base, DATABASE_URL, SessionLocal, engine, get_db
from .duplicates import RULE as DUPLICATE_RULE, DuplicateReviewError, find_duplicates, hide_confirmed_duplicates, restore_duplicates, restore_invalid_duplicate_links
from .connectors.camo import CAMOConnector, CamuError, camu_manager, timetable_window
from .connectors.camu_browser import MicrosoftSignIn
from .connectors.google_cal import GoogleCalendarConnector
from .connectors.google_cal import SCOPES, GoogleConnectionError, GoogleStateError, _configured_path, _credentials, create_login_url, finish_login
from .connectors.google_tasks import GoogleTasksConnector
from .connectors.lms import LMSConnector, lms_manager
from .connectors.lms_browser import LmsSignIn
from .connectors.base import Connector
from .connectors.outlook import OutlookConnector, outlook_manager
from .connectors.outlook_auth import OutlookError
from .models import Item, ItemPriority, ItemSource, ItemStatus, ItemType, WorkSession
from .item_payloads import ItemPayload, ManualItemPayload
from .manual_items import add_manual_item
from .csv_routes import router as csv_router
from .sync import SourceConfiguration, SyncCoordinator, SyncError, utc_iso
from .scheduler import create_scheduler
from .study import campus_now, campus_time
from .study_routes import router as study_router
from .day_planner import router as day_planner_router
from .oauth_redirect import google_return_url
from .item_sync import upsert_external_items, prune_camu_window
from .source_configuration import resolve_source_configuration
from .schema import initialize_schema
from .runtime import configure_logging, readiness, single_worker
from .private_access import PrivateAccessMiddleware, desktop_request
from .frontend import mount_frontend
from .session_queries import items_with_reservations, session_window, windowed_sessions
from .security_headers import documentation_html
from .outlook_routes import router as outlook_router
from .conflict_routes import router as conflict_router, check_manual_event, event_save_lock


@asynccontextmanager
async def lifespan(application):
    configure_logging()
    with single_worker(DATABASE_URL):
        initialize_schema(engine)
        sync_coordinator.initialize()
        try:
            interval = max(60, min(86400, int(os.getenv("AUTO_SYNC_INTERVAL_SECONDS", "300"))))
        except ValueError:
            interval = 300
        application.state.sync_interval = interval
        enabled = os.getenv("AUTO_SYNC_ENABLED", "true").lower() not in ("0", "false", "no", "off")
        application.state.sync_enabled = enabled
        scheduler = create_scheduler(lambda: sync_coordinator.run_all(automatic=True), interval) if enabled else None
        application.state.sync_scheduler = scheduler
        if scheduler:
            scheduler.start()
        try:
            yield
        finally:
            if scheduler:
                scheduler.shutdown(wait=True)
            camu_microsoft.close()
            lms_signin.close()


app = FastAPI(title="Calendar and Task Manager API", version="0.3.0", lifespan=lifespan,
              docs_url=None, redoc_url=None)


@app.get("/docs", include_in_schema=False)
def swagger_docs():
    return documentation_html(app)


@app.get("/redoc", include_in_schema=False)
def redoc_docs():
    return documentation_html(app, redoc=True)


app.include_router(study_router)
app.include_router(day_planner_router)
app.include_router(outlook_router)
app.include_router(conflict_router)
app.include_router(csv_router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(PrivateAccessMiddleware, origin=os.getenv("DAYMARK_PRIVATE_ORIGIN", ""),
                   user=os.getenv("DAYMARK_PRIVATE_USER", ""))
DbSession = Annotated[Session, Depends(get_db)]
def refresh_after_connection():
    scheduler = getattr(app.state, "sync_scheduler", None)
    if scheduler and scheduler.running:
        scheduler.modify_job("source_sync", next_run_time=datetime.now(timezone.utc))


camu_microsoft = MicrosoftSignIn(camu_manager, on_connected=refresh_after_connection)
lms_signin = LmsSignIn(lms_manager, on_connected=refresh_after_connection)


class SessionPayload(BaseModel):
    item_id: int
    start: datetime
    end: datetime

    @field_validator("start", "end")
    @classmethod
    def normalize_times(cls, value: datetime) -> datetime:
        return campus_time(value)

    @model_validator(mode="after")
    def validate_range(self) -> "SessionPayload":
        if self.end <= self.start:
            raise ValueError("end must be after start")
        return self


class ItemResponse(ItemPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    source: ItemSource
    source_id: str | None
    last_synced: datetime | None
    created_at: datetime
    updated_at: datetime
    duplicate_of_id: int | None = None
    reserved_minutes: int | None = Field(default=None, ge=0)

    @field_validator("subtasks", mode="before")
    @classmethod
    def decode_subtasks(cls, value: str | list[str]) -> list[str]:
        return json.loads(value) if isinstance(value, str) else value


class SessionResponse(SessionPayload):
    model_config = ConfigDict(from_attributes=True)
    id: int
    completed: bool


class SyncResponse(BaseModel):
    source: str
    imported: int
    updated: int


class SyncAllResponse(BaseModel):
    results: list[SyncResponse]
    errors: list[str]
    skipped: list[dict[str, str]] = Field(default_factory=list)
    busy: bool = False


class PriorityPayload(BaseModel):
    priority: ItemPriority


class StatusPayload(BaseModel):
    status: ItemStatus


class DuplicateCandidateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    keep: ItemResponse
    remove: ItemResponse
    fingerprint: str
    reason: str


class RemovedDuplicateResponse(BaseModel):
    item: ItemResponse
    keep: ItemResponse | None


class DuplicatePreviewResponse(BaseModel):
    candidates: list[DuplicateCandidateResponse]
    removed: list[RemovedDuplicateResponse]
    rule: str


class DuplicateChoice(BaseModel):
    keep_id: int = Field(gt=0)
    remove_id: int = Field(gt=0)
    fingerprint: str = Field(pattern="^[a-f0-9]{64}$")


class DuplicateRemovalPayload(BaseModel):
    confirmed: Literal[True]
    choices: list[DuplicateChoice] = Field(min_length=1, max_length=1000)


class DuplicateRestorePayload(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=1000)


class GoogleStatus(BaseModel):
    configured: bool
    connected: bool


class CamuLoginPayload(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: SecretStr = Field(min_length=1, max_length=1024)


class CamuOtpRequest(BaseModel):
    challenge_id: str = Field(min_length=20, max_length=100)
    method: str = Field(pattern="^(email|sms)$")


class CamuOtpVerify(BaseModel):
    challenge_id: str = Field(min_length=20, max_length=100)
    otp: SecretStr = Field(min_length=4, max_length=12)


class IntegrationStatus(BaseModel):
    key: str
    label: str
    configured: bool
    connected: bool
    detail: str
    live: bool = True


def initial_priority(due: datetime | None) -> ItemPriority:
    if due is None:
        return ItemPriority.MEDIUM
    days_left = (campus_time(due) - campus_now()).total_seconds() / 86400
    if days_left <= 2:
        return ItemPriority.HIGH
    if days_left <= 7:
        return ItemPriority.MEDIUM
    return ItemPriority.LOW


@app.get("/health")
def health(request: Request):
    result = readiness(engine, getattr(request.app.state, "sync_scheduler", None),
                       getattr(request.app.state, "sync_enabled", True))
    return JSONResponse(result, status_code=200 if result["status"] == "ok" else 503)


@app.get("/api/google/status", response_model=GoogleStatus)
def google_status() -> GoogleStatus:
    client_path = _configured_path("GOOGLE_CLIENT_SECRET_FILE", "credentials.json")
    token_path = _configured_path("GOOGLE_TOKEN_FILE", "google-token.json")
    connected = False
    if token_path.exists():
        try:
            from google.oauth2.credentials import Credentials

            credentials = Credentials.from_authorized_user_file(str(token_path), SCOPES)
            connected = bool(credentials.valid or credentials.refresh_token)
        except (ValueError, OSError):
            connected = False
    return GoogleStatus(configured=client_path.exists(), connected=connected)


@app.get("/api/google/login")
def google_login_page(request: Request) -> RedirectResponse:
    try:
        callback_url = str(request.base_url).rstrip("/") + "/api/google/callback"
        authorization_url, _ = create_login_url(callback_url)
    except Exception:
        raise HTTPException(status_code=502, detail="Google sign-in could not start. Check the connection settings and try again.") from None
    return RedirectResponse(authorization_url)


@app.get("/api/google/callback")
def google_callback(request: Request, state: str | None = None, error: str | None = None) -> RedirectResponse:
    frontend_url = os.getenv("FRONTEND_URL", "http://127.0.0.1:5173")
    if error:
        return RedirectResponse(google_return_url(frontend_url, error="access_denied" if error == "access_denied" else "provider_error"))
    if not state:
        return RedirectResponse(google_return_url(frontend_url, error="missing_state"))
    try:
        finish_login(state, str(request.url))
    except GoogleStateError:
        return RedirectResponse(google_return_url(frontend_url, error="invalid_state"))
    except Exception:
        return RedirectResponse(google_return_url(frontend_url, error="login_failed"))
    refresh_after_connection()
    return RedirectResponse(google_return_url(frontend_url))


@app.get("/api/integrations/status", response_model=list[IntegrationStatus])
def integrations_status() -> list[IntegrationStatus]:
    google = google_status()
    lms = lms_manager.status()
    camu = camu_manager.status()
    outlook = outlook_manager.status()
    return [
        IntegrationStatus(
            key="google",
            label="Google Calendar and Tasks",
            configured=google.configured,
            connected=google.connected,
            detail="Read-only Calendar and Tasks access" if google.connected else "Connect with Google OAuth",
        ),
        IntegrationStatus(
            key="lms",
            label="Bennett LMS",
            configured=lms["configured"],
            connected=lms["connected"],
            detail=lms["detail"],
            live=lms["live"],
        ),
        IntegrationStatus(
            key="camo",
            label="MyCamu",
            configured=camu["configured"],
            connected=camu["connected"],
            detail=camu["detail"],
        ),
        IntegrationStatus(key="outlook", label="Microsoft Outlook", configured=outlook["configured"],
                          connected=outlook["connected"], detail=outlook["detail"]),
    ]


@app.get("/api/camu/status")
def camu_status():
    return camu_manager.status()


@app.post("/api/camu/login")
def camu_login(payload: CamuLoginPayload):
    try:
        return camu_manager.login(payload.email, payload.password.get_secret_value())
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.post("/api/camu/microsoft/start")
def camu_microsoft_start(request: Request):
    if not desktop_request(request):
        raise HTTPException(status_code=400, detail="Start Microsoft sign-in on the computer running Daymark.")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(status_code=415, detail="Microsoft sign-in requires a JSON request.")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="Open Daymark locally to start Microsoft sign-in.")
    try:
        return camu_microsoft.start()
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.get("/api/camu/microsoft/{attempt_id}")
def camu_microsoft_status(attempt_id: str):
    try:
        return camu_microsoft.status(attempt_id)
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.delete("/api/camu/microsoft/{attempt_id}", status_code=status.HTTP_204_NO_CONTENT)
def camu_microsoft_cancel(attempt_id: str):
    try:
        camu_microsoft.cancel(attempt_id)
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.post("/api/camu/otp/request")
def camu_request_otp(payload: CamuOtpRequest):
    try:
        return camu_manager.request_otp(payload.challenge_id, payload.method)
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.post("/api/camu/otp/verify")
def camu_verify_otp(payload: CamuOtpVerify):
    try:
        return camu_manager.verify_otp(payload.challenge_id, payload.otp.get_secret_value())
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.delete("/api/camu/session", status_code=status.HTTP_204_NO_CONTENT)
def camu_disconnect():
    try:
        camu_microsoft.close()
        camu_manager.disconnect()
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


def perform_sync(source: ItemSource, db: Session) -> SyncResponse:
    connectors: dict[ItemSource, Connector] = {
        ItemSource.GOOGLE_CAL: GoogleCalendarConnector(),
        ItemSource.GOOGLE_TASKS: GoogleTasksConnector(),
        ItemSource.LMS: LMSConnector(),
        ItemSource.CAMO: CAMOConnector(),
        ItemSource.OUTLOOK: OutlookConnector(),
    }
    connector = connectors.get(source)
    if connector is None:
        raise HTTPException(status_code=400, detail="Manual items cannot be synced.")
    with outlook_manager.lock if source is ItemSource.OUTLOOK else nullcontext():
        try:
            external_items = connector.fetch()
        except (CamuError, GoogleConnectionError, OutlookError) as error:
            raise HTTPException(status_code=error.status_code, detail=str(error)) from None

        imported, updated = upsert_external_items(db, source, external_items, initial_priority)
        if source is ItemSource.CAMO:
            window_start, window_end = timetable_window()
            prune_camu_window(db, [external.source_id for external in external_items], window_start, window_end)
        if source is ItemSource.OUTLOOK:
            connector.save_snapshot(db, [external.source_id for external in external_items])
        db.flush()
        restore_invalid_duplicate_links(db)
        db.commit()
    return SyncResponse(source=source.value, imported=imported, updated=updated)


def file_revision(path):
    try:
        stat = path.stat()
        return f"{stat.st_mtime_ns}:{stat.st_size}"
    except OSError:
        return ""


def source_configuration(source):
    def google_configuration():
        return SourceConfiguration(google_status().connected, "live", file_revision(_configured_path("GOOGLE_TOKEN_FILE", "google-token.json")), "Read-only Google connection")

    def camu_configuration():
        camu = camu_manager.status()
        return SourceConfiguration(camu["connected"], "live", file_revision(camu_manager.session_file), camu["detail"])

    return resolve_source_configuration(
        source, google=google_configuration, camu=camu_configuration,
        lms=lambda: SourceConfiguration(**lms_manager.configuration()),
        outlook=lambda: SourceConfiguration(**outlook_manager.configuration()),
    )


sync_coordinator = SyncCoordinator(SessionLocal, perform_sync, source_configuration)


@app.get("/api/sync/status")
def automatic_sync_status():
    scheduler = getattr(app.state, "sync_scheduler", None)
    job = scheduler.get_job("source_sync") if scheduler and scheduler.running else None
    return {**sync_coordinator.status(), "enabled": bool(job), "interval_seconds": getattr(app.state, "sync_interval", 300), "next_run_at": utc_iso(job.next_run_time) if job else None}


@app.post("/api/sync/{source}", response_model=SyncResponse)
def sync_source(source: ItemSource, db: DbSession):
    try:
        return sync_coordinator.run_one(source, db)
    except SyncError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.post("/api/sync", response_model=SyncAllResponse)
def sync_all_sources():
    return sync_coordinator.run_all()


@app.get("/api/lms/status")
def lms_status():
    return lms_manager.status()


@app.post("/api/lms/connect/start")
def lms_connect_start(request: Request):
    if not desktop_request(request):
        raise HTTPException(status_code=400, detail="Start LMS sign-in on the computer running Daymark.")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(status_code=415, detail="LMS sign-in requires a JSON request.")
    origin = request.headers.get("origin")
    if origin and urlsplit(origin).hostname not in ("localhost", "127.0.0.1", "::1"):
        raise HTTPException(status_code=403, detail="Open Daymark locally to connect LMS.")
    try:
        return lms_signin.start()
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.get("/api/lms/connect/{attempt_id}")
def lms_connect_status(attempt_id: str):
    try:
        return lms_signin.status(attempt_id)
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.delete("/api/lms/connect/{attempt_id}")
def lms_connect_cancel(attempt_id: str):
    try:
        return lms_signin.cancel(attempt_id)
    except CamuError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None


@app.get("/api/items", response_model=list[ItemResponse])
def list_items(
    db: DbSession,
    item_type: ItemType | None = Query(default=None, alias="type"),
    item_status: ItemStatus | None = Query(default=None, alias="status"),
    source: ItemSource | None = None,
) -> list[Item]:
    query = select(Item).where(Item.duplicate_of_id.is_(None)).order_by(Item.start.asc(), Item.due.asc(), Item.id.asc())
    if item_type:
        query = query.where(Item.type == item_type)
    if item_status:
        query = query.where(Item.status == item_status)
    if source:
        query = query.where(Item.source == source)
    return items_with_reservations(db, query)


@app.get("/api/duplicates", response_model=DuplicatePreviewResponse)
def preview_duplicates(db: DbSession):
    removed = list(db.scalars(select(Item).where(Item.duplicate_of_id.is_not(None)).order_by(Item.start, Item.id)))
    keeper_ids = {item.duplicate_of_id for item in removed}
    keepers = {item.id: item for item in db.scalars(select(Item).where(Item.id.in_(keeper_ids)))} if keeper_ids else {}
    return {
        "candidates": find_duplicates(db),
        "removed": [{"item": item, "keep": keepers.get(item.duplicate_of_id)} for item in removed],
        "rule": DUPLICATE_RULE,
    }


@app.post("/api/duplicates/remove")
def remove_duplicates(payload: DuplicateRemovalPayload, db: DbSession):
    try:
        item_ids = hide_confirmed_duplicates(db, [choice.model_dump() for choice in payload.choices], payload.confirmed)
    except DuplicateReviewError as error:
        raise HTTPException(status_code=error.status_code, detail=str(error)) from None
    db.commit()
    return {"removed_count": len(item_ids), "item_ids": item_ids}


@app.post("/api/duplicates/restore")
def restore_removed_duplicates(payload: DuplicateRestorePayload, db: DbSession):
    item_ids = restore_duplicates(db, payload.item_ids)
    db.commit()
    return {"restored_count": len(item_ids), "item_ids": item_ids}


@app.get("/api/items/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: DbSession) -> Item:
    item = db.get(Item, item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


@app.post("/api/items", response_model=ItemResponse, status_code=status.HTTP_201_CREATED)
def create_item(payload: ManualItemPayload, db: DbSession) -> Item:
    with event_save_lock:
        item = add_manual_item(db, payload, initial_priority(payload.due))
        db.commit()
        db.refresh(item)
        return item


@app.patch("/api/items/{item_id}", response_model=ItemResponse)
def update_item(item_id: int, payload: ManualItemPayload, db: DbSession) -> Item:
    with event_save_lock:
        item = get_item(item_id, db)
        if item.source is not ItemSource.MANUAL:
            raise HTTPException(status_code=409, detail="Imported items are read-only.")
        check_manual_event(db, payload, item_id)
        values = payload.model_dump(exclude={"allow_conflict"})
        values["subtasks"] = json.dumps(values["subtasks"])
        for key, value in values.items():
            setattr(item, key, value)
        db.commit()
        db.refresh(item)
        return item


@app.patch("/api/items/{item_id}/priority", response_model=ItemResponse)
def update_item_priority(item_id: int, payload: PriorityPayload, db: DbSession) -> Item:
    item = get_item(item_id, db)
    item.priority = payload.priority
    db.commit()
    db.refresh(item)
    return item


@app.patch("/api/items/{item_id}/status", response_model=ItemResponse)
def update_item_status(item_id: int, payload: StatusPayload, db: DbSession) -> Item:
    item = get_item(item_id, db)
    if item.type is not ItemType.TASK:
        raise HTTPException(status_code=400, detail="Only tasks can be completed.")
    item.status = payload.status
    db.commit()
    db.refresh(item)
    return item


@app.get("/api/sessions", response_model=list[SessionResponse])
def list_sessions(db: DbSession, from_date: datetime | None = None, to_date: datetime | None = None) -> list[WorkSession]:
    start, end = session_window(campus_now(), from_date, to_date)
    return windowed_sessions(db, start, end)


@app.post("/api/sessions", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionPayload, db: DbSession) -> WorkSession:
    item = db.get(Item, payload.item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="Task not found")
    if item.type is not ItemType.TASK:
        raise HTTPException(status_code=400, detail="Study sessions require a task.")
    session = WorkSession(**payload.model_dump())
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.delete("/api/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_item(item_id: int, db: DbSession) -> None:
    item = get_item(item_id, db)
    if item.source is not ItemSource.MANUAL:
        raise HTTPException(status_code=409, detail="Imported items cannot be deleted.")
    db.delete(item)
    db.commit()


# Keep this after API routes: unknown API paths must never become index.html.
mount_frontend(app)
