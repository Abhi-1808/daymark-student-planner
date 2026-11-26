from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .models import Record


def demo_records(zone):
    now = datetime.now(ZoneInfo(zone))
    today = now.date()
    tomorrow = today + timedelta(days=1)
    monday = today - timedelta(days=today.weekday())

    def event(day, start, end, title, course, location, color, category="class"):
        first = datetime.combine(day, datetime.strptime(start, "%H:%M").time(), now.tzinfo)
        last = datetime.combine(day, datetime.strptime(end, "%H:%M").time(), now.tzinfo)
        return Record(kind="event", title=title, start=first.isoformat(), end=last.isoformat(),
                      course=course, category=category, location=location, color=color)

    courses = [
        ("CSE201", "Data Structures", "teal"),
        ("CSE245", "Database Systems", "violet"),
        ("MAT210", "Probability & Statistics", "blue"),
        ("CSE299", "Design Studio", "amber"),
    ]
    entries = {
        f"course-{code}": Record(kind="course", title=title, course=code, color=color)
        for code, title, color in courses
    }
    for index, (day, start, end, title, code, room, color, category) in enumerate([
        (today, "09:00", "10:00", "Data Structures", "CSE201", "Block B · 204", "teal", "class"),
        (today, "11:30", "12:30", "Database Systems Lab", "CSE245", "Lab 3", "violet", "class"),
        (today, "14:00", "15:00", "Probability & Statistics", "MAT210", "Block A · 106", "blue", "class"),
        (today, "16:00", "16:45", "Revise graph algorithms", "CSE201", "Library", "amber", "study"),
        (tomorrow, "10:00", "11:30", "Design Studio", "CSE299", "Studio 2", "amber", "class"),
        (monday + timedelta(days=8), "10:30", "12:00", "Database Systems midterm", "CSE245", "Exam hall", "rose", "exam"),
    ]):
        entries[f"event-{index}"] = event(day, start, end, title, code, room, color, category)
    for index, (title, course, delta, length, priority, done) in enumerate([
        ("Submit DBMS assignment", "CSE245", 0, 45, "high", False),
        ("Practice graph problems", "CSE201", 1, 60, "normal", False),
        ("Review conditional probability", "MAT210", 2, 30, "normal", False),
        ("Upload studio sketch", "CSE299", 0, 20, "low", True),
    ]):
        entries[f"task-{index}"] = Record(kind="task", title=title, course=course, done=done,
                due=(today + timedelta(days=delta)).isoformat(), priority=priority, minutes=length)
    for index in range(8):
        entries[f"attendance-{index}"] = Record(kind="attendance", title="Data Structures class",
            course="CSE201", due=(today - timedelta(days=index + 1)).isoformat(),
            attendance="absent" if index == 3 else "present")
    return entries
