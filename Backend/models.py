from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, Enum as SqlEnum, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class ItemType(str, Enum):
    EVENT = "event"
    TASK = "task"


class ItemStatus(str, Enum):
    PENDING = "pending"
    DONE = "done"


class ItemPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ItemSource(str, Enum):
    MANUAL = "manual"
    GOOGLE_CAL = "google_cal"
    GOOGLE_TASKS = "google_tasks"
    LMS = "lms"
    CAMO = "camo"
    OUTLOOK = "outlook"


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_item_source_source_id"),
        Index("ix_items_start", "start"),
        Index("ix_items_due", "due"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    type: Mapped[ItemType] = mapped_column(SqlEnum(ItemType), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    due: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[ItemStatus] = mapped_column(
        SqlEnum(ItemStatus), nullable=False, default=ItemStatus.PENDING
    )
    priority: Mapped[ItemPriority] = mapped_column(
        SqlEnum(ItemPriority), nullable=False, default=ItemPriority.MEDIUM
    )
    estimated_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    tiny_action: Mapped[str | None] = mapped_column(String(300))
    if_then_plan: Mapped[str | None] = mapped_column(String(500))
    subtasks: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    source: Mapped[ItemSource] = mapped_column(
        SqlEnum(ItemSource), nullable=False, default=ItemSource.MANUAL
    )
    source_id: Mapped[str | None] = mapped_column(String(500))
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("items.id", ondelete="SET NULL"), nullable=True)
    last_synced: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
        nullable=False,
    )


class WorkSession(Base):
    __tablename__ = "work_sessions"
    __table_args__ = (
        Index("ix_work_sessions_item_id", "item_id"),
        Index("ix_work_sessions_start", "start"),
        Index("ix_work_sessions_end", "end"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    completed: Mapped[bool] = mapped_column(default=False, nullable=False)


class SourceSyncState(Base):
    __tablename__ = "source_sync_states"
    source: Mapped[str] = mapped_column(String(30), primary_key=True)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="waiting")
    last_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    config_revision: Mapped[str | None] = mapped_column(String(200))
    imported: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class OutlookSnapshot(Base):
    """Bounded Outlook metadata; message bodies and attachments are never stored."""
    __tablename__ = "outlook_snapshots"
    owner: Mapped[str] = mapped_column(String(64), primary_key=True)
    events: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    messages: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class StudySubject(Base):
    __tablename__ = "study_subjects"
    key: Mapped[str] = mapped_column(String(120), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    links: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    item_ids: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    attended: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    target: Mapped[float] = mapped_column(nullable=False, default=75)


class StudyExam(Base):
    __tablename__ = "study_exams"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id", ondelete="CASCADE"), nullable=False, unique=True)
    subject_key: Mapped[str | None] = mapped_column(String(120))
    topics: Mapped[str] = mapped_column(Text, nullable=False)
    planned: Mapped[bool] = mapped_column(default=False, nullable=False)
