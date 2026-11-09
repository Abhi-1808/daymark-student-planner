"""Windowed schedule transport and compact task reservation totals."""

from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy import BigInteger, Integer, String, case, cast, func, select

from .models import Item, WorkSession
from .study import campus_time

DEFAULT_PAST_DAYS = 90
DEFAULT_FUTURE_DAYS = 91
MAX_WINDOW_DAYS = 366


def session_window(now, from_date=None, to_date=None):
    midnight = campus_time(now).replace(hour=0, minute=0, second=0, microsecond=0)
    try:
        start = campus_time(from_date) if from_date is not None else None
        end = campus_time(to_date) if to_date is not None else None
        if start is None:
            start = end - timedelta(days=DEFAULT_PAST_DAYS) if end is not None else midnight - timedelta(days=DEFAULT_PAST_DAYS)
        if end is None:
            end = start + timedelta(days=DEFAULT_PAST_DAYS) if from_date is not None else midnight + timedelta(days=DEFAULT_FUTURE_DAYS)
    except OverflowError:
        raise HTTPException(422, "Choose a session window within supported calendar dates.") from None
    if end <= start or end - start > timedelta(days=MAX_WINDOW_DAYS):
        raise HTTPException(422, "Choose a session window after its start and no longer than 366 days.")
    return start, end


def windowed_sessions(db, start, end):
    return list(db.scalars(select(WorkSession).where(
        WorkSession.end > start, WorkSession.start < end,
    ).order_by(WorkSession.start, WorkSession.id)))


def _microseconds(column, dialect):
    if dialect == "sqlite":
        # SQLite's Julian-day arithmetic loses precision at whole-minute
        # boundaries. Strip fractions before epoch conversion (which itself
        # rounds fractions), then add the stored microseconds as integers.
        stamp = cast(column, String)
        seconds = cast(func.strftime("%s", func.substr(stamp, 1, 19)), BigInteger)
        fraction = cast(func.substr(func.substr(stamp, 21, 6).concat("000000"), 1, 6), Integer)
        return seconds * 1_000_000 + fraction
    return cast(func.extract("epoch", column) * 1_000_000, BigInteger)


def items_with_reservations(db, query):
    items = list(db.scalars(query))
    if not items:
        return items
    dialect = db.get_bind().dialect.name
    elapsed = _microseconds(WorkSession.end, dialect) - _microseconds(WorkSession.start, dialect)
    # Match the planner: floor each positive block to whole minutes, then sum.
    minutes = case((elapsed > 0, elapsed // 60_000_000), else_=0)
    totals = dict(db.execute(select(WorkSession.item_id, func.sum(minutes)).where(
        WorkSession.item_id.in_(query.with_only_columns(Item.id).order_by(None)),
    ).group_by(WorkSession.item_id)).all())
    for item in items:
        item.reserved_minutes = int(totals.get(item.id, 0))
    return items
