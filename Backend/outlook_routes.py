"""Outlook account setup, bounded cached updates and explicitly chosen reminders."""

from datetime import datetime
import json
import os
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .connectors.outlook import outlook_manager, record_key
from .connectors.outlook_auth import OutlookError
from .connectors.outlook_desktop import desktop_request as read_desktop
from .database import get_db
from .models import Item, ItemPriority, ItemSource, ItemStatus, ItemType, OutlookSnapshot
from .oauth_redirect import outlook_return_url
from .private_access import desktop_request
from .study import campus_now, campus_time
from .sync import utc_iso

router = APIRouter(prefix="/api/outlook", tags=["Outlook"])
Db = Annotated[Session, Depends(get_db)]


class Registration(BaseModel):
    client_id: str = Field(max_length=36)
    tenant_id: str = Field(max_length=36)


class DesktopAccount(BaseModel):
    account: str = Field(default="", max_length=320)


class OpenDesktopItem(BaseModel):
    kind: Literal["event", "message"]
    item_id: str = Field(min_length=1, max_length=2000)


class EmailReminder(BaseModel):
    message_id: str = Field(min_length=1, max_length=2000)
    due: datetime

    @field_validator("due")
    @classmethod
    def future_deadline(cls, value):
        value = campus_time(value)
        if value <= campus_now():
            raise ValueError("Choose a future reminder time.")
        return value


def desktop_json(request):
    if not desktop_request(request):
        raise HTTPException(403, "Manage Microsoft sign-in on the computer running Daymark.")
    if request.headers.get("content-type", "").split(";")[0] != "application/json":
        raise HTTPException(415, "Outlook setup requires a JSON request.")


@router.get("/status")
def status():
    return outlook_manager.status()


@router.post("/login")
def login(payload: Registration, request: Request):
    desktop_json(request)
    try:
        outlook_manager.configure(payload.client_id, payload.tenant_id)
        port = request.url.port or 8000
        return {"authorization_url": outlook_manager.start(f"http://localhost:{port}/api/outlook/callback")}
    except OutlookError as error:
        raise HTTPException(error.status_code, str(error)) from None


@router.post("/desktop")
def connect_desktop(payload: DesktopAccount, request: Request):
    desktop_json(request)
    try:
        with outlook_manager.lock:
            profile = read_desktop("probe", account=payload.account)
            result = outlook_manager.connect_desktop(profile.get("account"), profile.get("offline", False))
        scheduler = getattr(request.app.state, "sync_scheduler", None)
        if scheduler and scheduler.running:
            from datetime import timezone
            scheduler.modify_job("source_sync", next_run_time=datetime.now(timezone.utc))
        return result
    except OutlookError as error:
        raise HTTPException(error.status_code, str(error)) from None


@router.post("/open")
def open_desktop_item(payload: OpenDesktopItem, request: Request, db: Db):
    desktop_json(request)
    with outlook_manager.lock:
        state = outlook_manager.status()
        snapshot = db.get(OutlookSnapshot, outlook_manager.owner()) if state.get("mode") == "desktop" else None
        records = json.loads(snapshot.events if payload.kind == "event" else snapshot.messages) if snapshot else []
        record = next((record for record in records if record["id"] == payload.item_id), None)
        if not record:
            raise HTTPException(404, "This item is no longer in your current Outlook snapshot.")
        entry_id = record.get("desktop_entry_id") if payload.kind == "event" else record["id"]
        try:
            return read_desktop("open", account=state["account"], entry_id=entry_id)
        except OutlookError as error:
            raise HTTPException(error.status_code, str(error)) from None


@router.get("/callback")
def callback(request: Request):
    frontend = os.getenv("FRONTEND_URL", "http://127.0.0.1:8000")
    try:
        outlook_manager.finish(str(request.url))
    except Exception:
        return RedirectResponse(outlook_return_url(frontend, error="login_failed"))
    scheduler = getattr(request.app.state, "sync_scheduler", None)
    if scheduler and scheduler.running:
        from datetime import timezone
        scheduler.modify_job("source_sync", next_run_time=datetime.now(timezone.utc))
    return RedirectResponse(outlook_return_url(frontend))


@router.delete("/connection")
def disconnect(request: Request, db: Db):
    desktop_json(request)
    with outlook_manager.lock:
        owner = outlook_manager.owner()
        outlook_manager.disconnect()
        if owner and (snapshot := db.get(OutlookSnapshot, owner)):
            db.delete(snapshot)
            db.commit()
    return {"connected": False}


@router.get("/updates")
def updates(db: Db):
    state = outlook_manager.status()
    owner = outlook_manager.owner() if state["connected"] else ""
    snapshot = db.get(OutlookSnapshot, owner) if owner else None
    messages = json.loads(snapshot.messages) if snapshot else []
    keys = [record_key(owner, message["id"], "outlook-mail") for message in messages]
    reminders = {item.source_id: item for item in db.scalars(select(Item).where(Item.source == ItemSource.MANUAL, Item.source_id.in_(keys)))} if keys else {}
    for message, key in zip(messages, keys):
        reminder = reminders.get(key)
        message["reminder"] = {"id": reminder.id, "due": reminder.due.isoformat(), "status": reminder.status.value} if reminder else None
    return {**state, "updated_at": utc_iso(snapshot.fetched_at) if snapshot else None,
            "events": json.loads(snapshot.events) if snapshot else [], "messages": messages}


@router.post("/reminders")
def email_reminder(payload: EmailReminder, db: Db):
    with outlook_manager.lock:
        owner = outlook_manager.owner()
        snapshot = db.get(OutlookSnapshot, owner) if owner else None
        message = next((value for value in json.loads(snapshot.messages) if value["id"] == payload.message_id), None) if snapshot else None
        if message is None:
            raise HTTPException(409, "Refresh Outlook and choose an email from its current snapshot.")
        key = record_key(owner, message["id"], "outlook-mail")
        item = db.scalar(select(Item).where(Item.source == ItemSource.MANUAL, Item.source_id == key))
        created = item is None
        if item is None:
            item = Item(source=ItemSource.MANUAL, source_id=key, type=ItemType.TASK,
                        title=("Follow up: " + message["subject"])[:300], due=payload.due,
                        description=f'Outlook email from {message["sender"]}\nOpen in Outlook: {message["web_url"]}',
                        status=ItemStatus.PENDING, priority=ItemPriority.MEDIUM, estimated_minutes=15)
            db.add(item)
            try:
                db.commit()
            except IntegrityError:
                db.rollback()
                item = db.scalar(select(Item).where(Item.source == ItemSource.MANUAL, Item.source_id == key))
                if item is None:
                    raise
                created = False
        return {"item_id": item.id, "created": created, "due": item.due.isoformat()}
