import csv
import hashlib
import io
import json
from datetime import date, datetime, timedelta
from itertools import islice
from zoneinfo import ZoneInfo

from icalendar import Calendar
import recurring_ical_events

from .models import Record

MAX_ROWS = 10000
CSV_FIELDS = tuple(Record.model_fields)
TEXT_FIELDS = ("title", "notes", "course", "location")
DATE_FIELDS = ("start", "end", "due", "repeat_until")
LIST_FIELDS = ("skip_days", "completed_days")
BOOLEAN_FIELDS = ("done", "busy")
FORMULA_PREFIX = "=+-@\t\r\n"


def identity(*parts):
    return hashlib.sha256(json.dumps(parts, separators=(",", ":")).encode()).hexdigest()


def bounds(zone, today=None):
    today = today or datetime.now(zone).date()
    start = datetime.combine(today - timedelta(days=60), datetime.min.time(), zone)
    end = datetime.combine(today + timedelta(days=365), datetime.min.time(), zone)
    return start, end


def text_value(value, limit):
    return str(value or "").strip()[:limit]


def parse_csv(raw, zone):
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""), strict=True)
    fields = reader.fieldnames or []
    if not {"kind", "title"}.issubset(fields):
        raise ValueError("CSV requires kind and title headers")
    if len(set(fields)) != len(fields):
        raise ValueError("CSV has duplicate headers")
    records = {}
    for position, row in enumerate(reader, start=2):
        if position > MAX_ROWS + 1:
            raise ValueError("CSV exceeds the 10,000 record limit")
        try:
            if None in row:
                raise ValueError("Too many columns")
            data = {key: value.strip() for key, value in row.items() if key in CSV_FIELDS and value}
            for key in TEXT_FIELDS:
                value = data.get(key, "")
                if value.startswith("'") and len(value) > 1 and value[1] in FORMULA_PREFIX:
                    data[key] = value[1:]
            for key in DATE_FIELDS:
                if key not in data or len(data[key]) == 10 or key not in ("start", "end"):
                    continue
                instant = datetime.fromisoformat(data[key])
                if instant.tzinfo is None:
                    instant = instant.replace(tzinfo=zone)
                data[key] = instant.isoformat()
            for key in LIST_FIELDS:
                if key in data:
                    data[key] = json.loads(data[key])
            record = Record.model_validate(data)
            key = row.get("external_id") or identity(record.kind, record.title.casefold(),
                record.start, record.end, record.due, record.course.casefold())
            if key in records and records[key] != record:
                raise ValueError("Conflicting rows share the same identity")
            records[key] = record
        except (TypeError, ValueError) as error:
            message = error.errors()[0]["msg"] if hasattr(error, "errors") else str(error)
            raise ValueError(f"CSV row {position}: {message}") from error
    return records


def write_csv(records):
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, (*CSV_FIELDS, "source"))
    writer.writeheader()
    for record in records:
        row = {key: record[key] for key in (*CSV_FIELDS, "source")}
        for key in TEXT_FIELDS:
            value = row[key]
            if value and value[0] in FORMULA_PREFIX:
                row[key] = "'" + value
        for key in LIST_FIELDS:
            row[key] = json.dumps(row[key], separators=(",", ":"))
        writer.writerow(row)
    return stream.getvalue()


def event_date(value, zone):
    if isinstance(value, datetime) and value.tzinfo is None:
        value = value.replace(tzinfo=zone)
    return value.isoformat()


def parse_ics(raw, zone, source, today=None):
    calendar = Calendar.from_ical(raw)
    start, end = bounds(zone, today)
    occurrences = recurring_ical_events.of(calendar, components=("VEVENT", "VTODO")).between(start, end)
    records = {}
    for index, item in enumerate(islice(occurrences, MAX_ROWS + 1)):
        if index >= MAX_ROWS:
            raise ValueError("Calendar exceeds the 10,000 occurrence limit")
        status = str(item.get("STATUS", "")).upper()
        if status == "CANCELLED":
            continue
        title = text_value(item.get("SUMMARY"), 200) or "Untitled item"
        notes = text_value(item.get("DESCRIPTION"), 10000)
        location = text_value(item.get("LOCATION"), 200)
        if item.name == "VTODO":
            due = item.decoded("DUE", None)
            day = due.astimezone(zone).date() if isinstance(due, datetime) and due.tzinfo else (
                due.date() if isinstance(due, datetime) else due)
            record = Record(kind="task", title=title, due=day.isoformat() if day else None,
                            notes=notes, category="assignment", done=status == "COMPLETED")
            anchor = str(item.decoded("RECURRENCE-ID", due))
        else:
            first = item.decoded("DTSTART", None)
            if not isinstance(first, date):
                continue
            last = item.decoded("DTEND", None)
            if last is None:
                last = first + item.decoded("DURATION", timedelta(days=1) if not isinstance(first, datetime) else timedelta(minutes=30))
            if last == first:
                last += timedelta(minutes=1) if isinstance(first, datetime) else timedelta(days=1)
            start_text, end_text = event_date(first, zone), event_date(last, zone)
            record = Record(kind="event", title=title, notes=notes, location=location,
                            start=start_text, end=end_text,
                            category={"bennett-lms": "assignment", "camu": "class"}.get(source, "personal"),
                            busy=str(item.get("TRANSP", "")).upper() != "TRANSPARENT")
            anchor = event_date(item.decoded("RECURRENCE-ID", first), zone)
        uid = str(item.get("UID", "")) or identity(title, location)
        records[identity(item.name, uid, anchor)] = record
    return records
