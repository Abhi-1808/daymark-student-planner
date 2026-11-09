"""Count safe sync-failure events in supplied JSON logs; standard library only."""

import argparse
from datetime import datetime, timedelta, timezone
import json

SOURCES = ("google_cal", "google_tasks", "lms", "camo", "outlook")


def summarize(lines, *, start, end):
    counts = {source: 0 for source in SOURCES}
    for line in lines:
        try:
            event = json.loads(line)
            if not isinstance(event, dict) or event.get("event") != "daymark.sync.failed" or event.get("source") not in counts:
                continue
            timestamp = datetime.fromisoformat(event["time"].replace("Z", "+00:00"))
            if timestamp.tzinfo is not None and start <= timestamp <= end:
                counts[event["source"]] += 1
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return {"start": start.isoformat(), "end": end.isoformat(), "total": sum(counts.values()), "by_source": counts}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("logs", nargs="+", help="One or more saved Daymark JSON log files")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    if not 1 <= args.days <= 365:
        parser.error("Choose a report window between 1 and 365 days.")
    end = datetime.now(timezone.utc)

    def lines():
        for filename in args.logs:
            with open(filename, encoding="utf-8", errors="replace") as stream:
                yield from stream

    try:
        report = summarize(lines(), start=end - timedelta(days=args.days), end=end)
    except OSError:
        parser.error("A log file could not be read. Check the paths and permissions.")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
