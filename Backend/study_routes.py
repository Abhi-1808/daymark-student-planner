from datetime import datetime, timedelta
import json
import re
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, HttpUrl, model_validator
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import Item, ItemPriority, ItemSource, ItemStatus, ItemType, StudyExam, StudySubject, WorkSession
from .preview_store import PreviewStore
from .slot_allocation import BREAK_MINUTES
from .study import campus_now, campus_time, plan_fingerprint, revision_horizon, revision_plan

router = APIRouter(prefix="/api/study", tags=["Study planning"])
DbSession = Annotated[Session, Depends(get_db)]
previews = PreviewStore()
plan_lock = previews.lock


class SubjectPayload(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    notes: str | None = Field(default=None, max_length=20000)
    links: list[HttpUrl] | None = Field(default=None, max_length=30)
    item_ids: list[int] | None = Field(default=None, max_length=2000)
    attended: int | None = Field(default=None, ge=0, le=100000)
    total: int | None = Field(default=None, ge=0, le=100000)
    target: float | None = Field(default=None, gt=0, le=100)


def subject_data(subject):
    return {"key": subject.key, "name": subject.name, "notes": subject.notes, "links": json.loads(subject.links), "item_ids": json.loads(subject.item_ids), "attended": subject.attended, "total": subject.total, "target": subject.target}


@router.get("/subjects")
def subjects(db: DbSession):
    return [subject_data(subject) for subject in db.scalars(select(StudySubject).order_by(StudySubject.name))]


@router.put("/subjects/{key}")
def save_subject(key: str, payload: SubjectPayload, db: DbSession):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,119}", key):
        raise HTTPException(422, "Use a valid subject key.")
    subject = db.get(StudySubject, key)
    attended = payload.attended if payload.attended is not None else subject.attended if subject else 0
    total = payload.total if payload.total is not None else subject.total if subject else 0
    if attended > total:
        raise HTTPException(422, "Attended classes cannot exceed total classes.")
    if subject is None:
        subject = StudySubject(key=key, name=payload.name, attended=attended, total=total)
        db.add(subject)
    subject.name = payload.name.strip()
    if not subject.name:
        raise HTTPException(422, "Enter a subject name.")
    for key_name in ("notes", "attended", "total", "target"):
        value = getattr(payload, key_name)
        if value is not None:
            setattr(subject, key_name, value)
    if payload.links is not None:
        subject.links = json.dumps([str(url) for url in payload.links])
    if payload.item_ids is not None:
        existing = set(db.scalars(select(Item.id).where(Item.id.in_(payload.item_ids))))
        if len(existing) != len(set(payload.item_ids)):
            raise HTTPException(422, "A related item no longer exists. Refresh and try again.")
        subject.item_ids = json.dumps(sorted(existing))
    db.commit()
    db.refresh(subject)
    return subject_data(subject)


class Topic(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    minutes: int = Field(default=30, ge=5, le=600, multiple_of=5)


class ExamPayload(BaseModel):
    item_id: int | None = None
    title: str = Field(default="", max_length=300)
    at: datetime | None = None
    duration_minutes: int = Field(default=60, ge=5, le=720)
    subject_key: str | None = Field(default=None, max_length=120)
    topics: list[Topic] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def validate_exam(self):
        if not self.item_id and (not self.title.strip() or not self.at):
            raise ValueError("Choose a calendar event or enter an exam title and time.")
        if any(not topic.name.strip() for topic in self.topics):
            raise ValueError("Each topic needs a name.")
        return self


def exam_data(exam, item):
    return {"id": exam.id, "item_id": item.id, "title": item.title, "at": item.start, "subject_key": exam.subject_key, "topics": json.loads(exam.topics), "planned": exam.planned}


@router.get("/exams")
def exams(db: DbSession):
    return [exam_data(exam, item) for exam, item in db.execute(select(StudyExam, Item).join(Item, Item.id == StudyExam.item_id).order_by(Item.start))]


@router.post("/exams", status_code=201)
def create_exam(payload: ExamPayload, db: DbSession):
    if payload.item_id:
        item = db.get(Item, payload.item_id)
        if not item or item.type != ItemType.EVENT or not item.start:
            raise HTTPException(422, "Choose an existing timed event for the exam.")
        if db.scalar(select(StudyExam.id).where(StudyExam.item_id == item.id)):
            raise HTTPException(409, "This exam already has a revision plan.")
    else:
        at = campus_time(payload.at)
        item = Item(type=ItemType.EVENT, title=payload.title.strip(), start=at, end=at + timedelta(minutes=payload.duration_minutes), source=ItemSource.MANUAL, priority=ItemPriority.HIGH)
        db.add(item)
        db.flush()
    if campus_time(item.start) <= campus_now() or campus_time(item.start) > campus_now() + timedelta(days=366):
        raise HTTPException(422, "Choose an exam within the next year.")
    exam = StudyExam(item_id=item.id, subject_key=payload.subject_key, topics=json.dumps([topic.model_dump() for topic in payload.topics]))
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam_data(exam, item)


class RevisionPreferences(BaseModel):
    start_hour: int = Field(default=9, ge=0, le=23)
    end_hour: int = Field(default=18, ge=1, le=24)
    buffer_minutes: int = Field(default=10, ge=0, le=60)

    @model_validator(mode="after")
    def validate_hours(self):
        if self.end_hour <= self.start_hour:
            raise ValueError("Study hours must end after they start.")
        return self


def exam_context(db, exam_id, *, horizon=None, buffer_minutes=10, now=None):
    exam = db.get(StudyExam, exam_id)
    item = db.get(Item, exam.item_id) if exam else None
    if not item:
        raise HTTPException(404, "Exam not found.")
    if exam.planned:
        raise HTTPException(409, "Revision sessions for this exam have already been added.")
    if horizon is None:
        horizon = revision_horizon(item.start, now if now is not None else campus_now(), buffer_minutes)
    start, end = horizon
    if end <= start:
        return exam, item, [item], [], horizon
    event_padding = timedelta(minutes=buffer_minutes)
    session_padding = timedelta(minutes=BREAK_MINUTES)
    events = list(db.scalars(select(Item).where(or_(
        Item.id == item.id,
        and_(Item.type == ItemType.EVENT, Item.duplicate_of_id.is_(None),
             Item.end > start - event_padding, Item.start < end + event_padding),
    ))))
    sessions = list(db.scalars(select(WorkSession).where(
        WorkSession.end > start - session_padding,
        WorkSession.start < end + session_padding,
    )))
    return exam, item, events, sessions, horizon


@router.post("/exams/{exam_id}/preview")
def preview_revision(exam_id: int, payload: RevisionPreferences, db: DbSession):
    now = campus_now()
    exam, item, events, sessions, horizon = exam_context(db, exam_id, buffer_minutes=payload.buffer_minutes, now=now)
    result = revision_plan(json.loads(exam.topics), events, sessions, item.start, now=now, start_hour=payload.start_hour, end_hour=payload.end_hour, buffer_minutes=payload.buffer_minutes)
    with plan_lock:
        token, expires = previews.issue({"exam_id": exam_id, "fingerprint": plan_fingerprint(events, sessions, exam), "result": result,
                                        "horizon": horizon, "buffer_minutes": payload.buffer_minutes}, now)
    return {**result, "token": token, "expires_at": expires.isoformat()}


class RevisionConfirmation(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    confirmed: bool


@router.post("/exams/{exam_id}/plan", status_code=201)
def confirm_revision(exam_id: int, payload: RevisionConfirmation, db: DbSession):
    if not payload.confirmed:
        raise HTTPException(400, "Review and confirm the revision preview first.")
    with plan_lock:
        preview = previews.get_valid(payload.token, campus_now())
        if preview is None or preview["exam_id"] != exam_id:
            raise HTTPException(409, "This preview expired. Generate a new preview.")
        exam, item, events, sessions, _ = exam_context(db, exam_id, horizon=preview["horizon"], buffer_minutes=preview["buffer_minutes"])
        if plan_fingerprint(events, sessions, exam) != preview["fingerprint"]:
            raise HTTPException(409, "Your calendar changed. Preview the revision sessions again.")
        proposed = preview["result"]["sessions"]
        if not proposed or any(datetime.fromisoformat(session["start"]) <= campus_now() for session in proposed):
            raise HTTPException(409, "No future sessions are available in this preview. Generate a new preview.")
        tasks = {}
        for session in proposed:
            index = session["topic_index"]
            if index not in tasks:
                topic = json.loads(exam.topics)[index]
                task = Item(type=ItemType.TASK, title=f"Revise: {topic['name']}"[:300], description=f"Revision for {item.title}", due=campus_time(item.start), estimated_minutes=topic["minutes"], priority=ItemPriority.HIGH, source=ItemSource.MANUAL)
                db.add(task)
                db.flush()
                tasks[index] = task
            db.add(WorkSession(item_id=tasks[index].id, start=datetime.fromisoformat(session["start"]), end=datetime.fromisoformat(session["end"])))
        exam.planned = True
        db.commit()
        previews.discard(payload.token)
    return {"sessions_created": len(proposed), "tasks_created": len(tasks)}
