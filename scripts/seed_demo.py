"""Create a separate synthetic demo database; leave existing databases untouched."""

import argparse
from datetime import date, datetime, time, timedelta, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DEMO_NOTE = "Synthetic team demonstration data. No real student record or source account."


def seed_demo(path, reference):
    from sqlalchemy import create_engine
    from sqlalchemy.engine import URL
    from sqlalchemy.orm import Session
    from Backend.database import Base
    from Backend.models import Item, ItemPriority, ItemSource, ItemStatus, ItemType, StudyExam, StudySubject, WorkSession

    path = Path(path).resolve()
    if path.name != "daymark-demo.db":
        raise ValueError("Demo data can only be written to daymark-demo.db.")
    if path.exists():
        return False
    engine = create_engine(URL.create("sqlite", database=str(path)))
    try:
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            monday = reference - timedelta(days=reference.weekday())
            for offset in range(5):
                day = monday + timedelta(days=offset)
                start = datetime.combine(day, time(9))
                for source, title in (
                    (ItemSource.CAMO, "Demo Calculus( P-CC-121 )"),
                    (ItemSource.GOOGLE_CAL, "Demo Calculus - Lecture"),
                ):
                    db.add(Item(type=ItemType.EVENT, title=title, description=DEMO_NOTE + "\nRoom: P-CC-121", source=source,
                                source_id=f"demo-calculus-{source.value}-{offset}", start=start, end=start + timedelta(hours=1)))
                db.add(Item(type=ItemType.EVENT, title="Demo Programming( B-LA-204 )", description=DEMO_NOTE,
                            source=ItemSource.CAMO, source_id=f"demo-programming-{offset}",
                            start=start.replace(hour=10, minute=5), end=start.replace(hour=11)))
            db.add(Item(type=ItemType.EVENT, title="Demo workshop", description=DEMO_NOTE,
                        source=ItemSource.MANUAL, source_id="demo-workshop",
                        start=datetime.combine(monday + timedelta(days=4), time(9, 30)),
                        end=datetime.combine(monday + timedelta(days=4), time(10, 30))))
            worksheet = Item(type=ItemType.TASK, title="Demo Calculus worksheet", description=DEMO_NOTE,
                             source=ItemSource.LMS, source_id="demo-worksheet", priority=ItemPriority.HIGH,
                             due=datetime.combine(reference + timedelta(days=1), time(17)), estimated_minutes=20)
            reading = Item(type=ItemType.TASK, title="Read demo programming chapter", description=DEMO_NOTE,
                           source=ItemSource.MANUAL, source_id="demo-reading", priority=ItemPriority.MEDIUM,
                           due=datetime.combine(reference + timedelta(days=2), time(17)), estimated_minutes=60)
            done = Item(type=ItemType.TASK, title="Completed demo exercise", description=DEMO_NOTE,
                        source=ItemSource.MANUAL, source_id="demo-completed", status=ItemStatus.DONE,
                        due=datetime.combine(reference, time(17)), estimated_minutes=15)
            exam = Item(type=ItemType.EVENT, title="Demo Calculus midterm", description=DEMO_NOTE,
                        source=ItemSource.MANUAL, source_id="demo-exam", priority=ItemPriority.HIGH,
                        start=datetime.combine(reference + timedelta(days=5), time(10)),
                        end=datetime.combine(reference + timedelta(days=5), time(11)))
            db.add_all([worksheet, reading, done, exam])
            db.flush()
            db.add(WorkSession(item_id=reading.id, start=datetime.combine(reference + timedelta(days=1), time(14)),
                               end=datetime.combine(reference + timedelta(days=1), time(14, 30))))
            db.add(StudySubject(key="demo-calculus", name="Demo Calculus", notes="Demo notes: revise limits and integration.",
                                links="[]", item_ids=json.dumps([worksheet.id, exam.id]), attended=18, total=25, target=75))
            db.add(StudySubject(key="demo-programming", name="Demo Programming", notes="Demo notes: review loops.",
                                links="[]", item_ids=json.dumps([reading.id]), attended=24, total=30, target=75))
            db.add(StudyExam(item_id=exam.id, subject_key="demo-calculus", topics=json.dumps([
                {"name": "Limits", "minutes": 45}, {"name": "Integration", "minutes": 60},
                {"name": "Practice paper", "minutes": 45},
            ])))
            db.commit()
    finally:
        engine.dispose()
    return True


def main():
    today = datetime.now(timezone(timedelta(hours=5, minutes=30))).date()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=today, help="Reference date in YYYY-MM-DD format.")
    arguments = parser.parse_args()
    created = seed_demo(ROOT / "daymark-demo.db", arguments.date)
    print("Created synthetic daymark-demo.db." if created else "daymark-demo.db already exists; left unchanged.")
    print("To use it in PowerShell, set these in the backend terminal:")
    print('$env:DATABASE_URL = "sqlite:///./daymark-demo.db"')
    print('$env:AUTO_SYNC_ENABLED = "false"')
    print("Then start the backend and frontend using START_HERE.md or README.md.")


if __name__ == "__main__":
    main()
