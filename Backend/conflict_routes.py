"""Bounded timetable checks and validation before manual events are saved."""

from datetime import datetime, timedelta
from threading import RLock
from types import SimpleNamespace
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from .conflicts import find_conflicts, timestamp
from .database import get_db
from .duplicates import duplicate_candidates
from .models import Item, ItemType
from .study import campus_time

router = APIRouter(tags=["Timetable checks"])
event_save_lock = RLock()


def window_events(db, start, end, padding=0):
    gap = timedelta(minutes=padding)
    return list(db.scalars(select(Item).where(
        Item.type == ItemType.EVENT, Item.duplicate_of_id.is_(None),
        Item.end > start - gap, Item.start < end + gap,
    ).order_by(Item.start, Item.id)))


def event_summary(event):
    return jsonable_encoder({key: getattr(event, key) for key in
            ("id", "type", "source", "title", "description", "start", "end", "status", "priority")})


def check_manual_event(db, payload, identifier=None):
    if payload.type != ItemType.EVENT or payload.allow_conflict or payload.start is None or payload.end is None or payload.end <= payload.start:
        return
    candidate = SimpleNamespace(**payload.model_dump(exclude={"allow_conflict"}), id=identifier)
    events = window_events(db, payload.start, payload.end)
    conflicts = find_conflicts(events, candidate, walking_minutes=0, duplicate_candidates=duplicate_candidates(events))
    if conflicts:
        ids = {record[key] for record in conflicts for key in ("a", "b") if record[key] != identifier}
        raise HTTPException(409, {"code": "event_conflict", "message": "This event overlaps your schedule. Change its time or choose Save anyway.",
                                  "conflicts": conflicts, "events": [event_summary(event) for event in events if event.id in ids]})


@router.get("/api/conflicts")
def timetable_conflicts(db: Annotated[Session, Depends(get_db)],
                        from_date: datetime = Query(alias="from"), to_date: datetime = Query(alias="to"),
                        walking_minutes: int = Query(default=10, ge=0, le=60)):
    start, end = campus_time(from_date), campus_time(to_date)
    if not timedelta(0) < end - start <= timedelta(days=93):
        raise HTTPException(422, "Choose a timetable-check window between zero and 93 days.")
    events = window_events(db, start, end, walking_minutes)
    records = find_conflicts(events, walking_minutes=walking_minutes, duplicate_candidates=duplicate_candidates(events))
    lookup = {event.id: event for event in events}
    # Padding allows a short room change across a window boundary, but never
    # adds a warning for two events that both lie outside the requested dates.
    records = [record for record in records if any(
        timestamp(lookup[record[key]].start) < end and timestamp(lookup[record[key]].end) > start for key in ("a", "b"))]
    used = {record[key] for record in records for key in ("a", "b")}
    return {"conflicts": records, "events": [event_summary(event) for event in events if event.id in used],
            "from": start, "to": end, "walking_minutes": walking_minutes}
