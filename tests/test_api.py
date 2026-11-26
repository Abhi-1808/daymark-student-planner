import os
import tempfile
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

import httpx
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.main import create_app
from backend.models import Record
from backend.store import Store
from backend.transfer import parse_ics


ORIGIN = "http://localhost:8000"


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        with patch.dict(os.environ, {
            "DAYMARK_ORIGIN": ORIGIN, "DAYMARK_DB": str(Path(self.temp.name) / "daymark.sqlite3"),
            "DAYMARK_SYNC_SECONDS": "0", "DAYMARK_PASSWORD": "", "DAYMARK_CAMU_FILE": "",
            "DAYMARK_BENNETT_ICS": "", "DAYMARK_GOOGLE_CLIENT_ID": "", "DAYMARK_GOOGLE_CLIENT_SECRET": "",
            "DAYMARK_MICROSOFT_CLIENT_ID": "", "DAYMARK_MICROSOFT_CLIENT_SECRET": "", "DAYMARK_TOKEN_KEY": "",
        }):
            self.config = Settings()

    def client(self, transport=None):
        return TestClient(create_app(self.config, transport), base_url=ORIGIN, headers={"Origin": ORIGIN})

    def test_record_lifecycle_persistence_and_separate_sources(self):
        with self.client() as client:
            created = client.post("/api/records", json={"kind": "task", "title": "DBMS notes", "due": "2026-11-26"}).json()
            record = {k: v for k, v in created.items() if k not in ("source", "id")}
            record["done"] = True
            self.assertEqual(client.put(f"/api/records/{created['id']}", json=record).status_code, 200)
        with self.client() as client:
            data = client.get("/api/workspace").json()
            self.assertTrue(data["records"][0]["done"])
            self.assertEqual(client.delete(f"/api/records/{created['id']}").status_code, 200)
            self.assertEqual(client.get("/api/workspace").json()["records"], [])

    def test_authentication_origin_and_host_checks(self):
        self.config.password = " a test password "
        with self.client() as client:
            self.assertEqual(client.get("/api/workspace").status_code, 401)
            self.assertEqual(client.post("/api/login", json={"password": self.config.password.strip()}).status_code, 401)
            login = client.post("/api/login", json={"password": self.config.password})
            self.assertIn("HttpOnly", login.headers["set-cookie"])
            self.assertEqual(client.post("/api/demo", headers={"Origin": "http://example.com"}).status_code, 403)
            self.assertEqual(client.get("/api/workspace", headers={"Host": "example.com"}).status_code, 400)
            self.assertEqual(client.get("/api/workspace").headers["cache-control"], "no-store")
            self.assertEqual(client.post("/api/logout").status_code, 200)
            self.assertEqual(client.get("/api/workspace").status_code, 401)

    def test_import_is_atomic_repeatable_read_only_and_export_safe(self):
        with self.client() as client:
            path = "/api/import/camu?format=csv"
            content = b"kind,title,course,due,external_id\ntask,=2+3,CSE245,2026-11-27,task1\n"
            invalid = content + b"task,Bad,CSE245,not-a-date,task2\n"
            bad = client.post(path, content=invalid)
            self.assertEqual(bad.status_code, 422)
            self.assertIn("CSV row 3", bad.json()["detail"])
            self.assertEqual(client.get("/api/workspace").json()["records"], [])
            self.assertEqual(client.post(path, content=content).json()["count"], 1)
            original = client.get("/api/workspace").json()
            self.assertEqual(client.post(path, content=content).status_code, 200)
            self.assertEqual(client.get("/api/workspace").json()["revision"], original["revision"])
            record = original["records"][0]
            self.assertEqual(client.delete(f"/api/records/{record['id']}").status_code, 404)
            export = client.get("/api/export.csv")
            self.assertIn("'=2+3", export.text)
            self.assertEqual(client.post("/api/import/csv?format=csv", content=export.content).status_code, 200)
            self.assertEqual([r["title"] for r in client.get("/api/workspace").json()["records"]], ["=2+3", "=2+3"])

    def test_plan_rejects_stale_or_repeated_confirmation(self):
        with self.client() as client:
            first = datetime.now(timezone.utc) + timedelta(hours=1)
            block = {"kind": "event", "title": "Review SQL", "category": "study",
                     "start": first.isoformat(), "end": (first + timedelta(minutes=30)).isoformat()}
            revision = client.get("/api/workspace").json()["revision"]
            now = int(time.time() * 1000)
            payload = {"revision": revision, "created": now, "blocks": [block]}
            self.assertEqual(client.post("/api/plan", json={**payload, "created": now - 310000}).status_code, 409)
            self.assertEqual(client.post("/api/plan", json={**payload, "blocks": [block, block]}).status_code, 422)
            self.assertEqual(client.post("/api/plan", json=payload).json()["count"], 1)
            self.assertEqual(client.post("/api/plan", json=payload).status_code, 409)
            self.assertEqual(len(client.get("/api/workspace").json()["records"]), 1)

    def test_oauth_state_refresh_and_failed_sync_preserve_last_data(self):
        self.config.key = Fernet.generate_key().decode()
        self.config.google_id = "test-client"
        self.config.google_secret = "test-secret"
        state = {"broken": False, "requests": []}

        def handler(request):
            state["requests"].append(request)
            path = request.url.path
            if path == "/token":
                grant = parse_qs(request.content.decode())
                if grant["grant_type"] == ["authorization_code"]:
                    self.assertIn("code_verifier", grant)
                    return httpx.Response(200, json={"access_token": "live", "refresh_token": "refresh", "expires_in": 1})
                self.assertEqual(grant["refresh_token"], ["refresh"])
                return httpx.Response(200, json={"access_token": "renewed", "expires_in": 3600})
            if path.endswith("/calendarList"):
                if state["broken"]:
                    return httpx.Response(503, json={})
                if "pageToken" not in request.url.params:
                    return httpx.Response(200, json={"items": [], "nextPageToken": "second"})
                return httpx.Response(200, json={"items": [{"id": "primary"}]})
            if path.endswith("/events"):
                return httpx.Response(200, json={"items": [{"id": "event", "summary": "Remote event",
                    "start": {"date": "2026-11-27"}, "end": {"date": "2026-11-28"}}]})
            if path.endswith("/lists"):
                return httpx.Response(200, json={"items": [{"id": "list"}]})
            if path.endswith("/tasks"):
                return httpx.Response(200, json={"items": [{"id": "task", "title": "Remote task",
                    "due": "2026-11-27T00:00:00Z", "status": "completed"}]})
            self.fail(str(request.url))

        with self.client(httpx.MockTransport(handler)) as client:
            result = client.post("/api/connections/google/start").json()
            query = parse_qs(urlsplit(result["url"]).query)
            self.assertEqual(query["code_challenge_method"], ["S256"])
            endpoint = "/api/connections/google/callback"
            self.assertEqual(client.get(endpoint, params={"code": "yes", "state": "wrong"}).status_code, 400)
            valid = {"code": "yes", "state": query["state"][0]}
            response = client.get(endpoint, params=valid, follow_redirects=False)
            self.assertEqual(response.status_code, 303)
            self.assertEqual(client.get(endpoint, params=valid).status_code, 400)
            workspace = client.get("/api/workspace").json()
            self.assertEqual({row["source"] for row in workspace["records"]}, {"google-calendar", "google-tasks"})
            self.assertNotIn("access_token", client.get("/api/workspace").text)
            cipher = Store(self.config.db).connection("google")["token"]
            self.assertNotIn("refresh", cipher)
            state["broken"] = True
            self.assertTrue(client.post("/api/connections/google/sync").json()["error"])
            self.assertEqual(client.get("/api/workspace").json()["records"], workspace["records"])
            self.assertEqual(client.delete("/api/connections/google").status_code, 200)
            self.assertEqual(client.get("/api/workspace").json()["records"], [])

    def test_microsoft_sync_normalizes_all_day_outside_utc_and_fetches_headers(self):
        self.config.key = Fernet.generate_key().decode()
        self.config.microsoft_id = "test-client"
        self.config.microsoft_secret = "test-secret"
        self.config.microsoft_mail = True

        def handler(request):
            path = request.url.path
            if path.endswith("/token"):
                return httpx.Response(200, json={"access_token": "test", "refresh_token": "refresh"})
            if path.endswith("/calendars"):
                return httpx.Response(200, json={"value": [{"id": "primary"}]})
            if path.endswith("/calendarView"):
                return httpx.Response(200, json={"value": [{
                    "id": "day", "subject": "Day off", "isAllDay": True, "showAs": "free",
                    "start": {"dateTime": "2026-11-26T18:30:00.0000000", "timeZone": "UTC"},
                    "end": {"dateTime": "2026-11-27T18:30:00.0000000", "timeZone": "UTC"},
                    "originalStartTimeZone": "India Standard Time", "originalEndTimeZone": "India Standard Time",
                }]})
            if path.endswith("/messages"):
                return httpx.Response(200, json={"value": [{"id": "message", "subject": "Room update",
                    "from": {"emailAddress": {"address": "fixture@example.test"}}, "body": "private body"}]})
            self.fail(str(request.url))

        with self.client(httpx.MockTransport(handler)) as client:
            query = parse_qs(urlsplit(client.post("/api/connections/microsoft/start").json()["url"]).query)
            self.assertIn("Mail.ReadBasic", query["scope"][0])
            result = client.get("/api/connections/microsoft/callback",
                params={"code": "yes", "state": query["state"][0]}, follow_redirects=False)
            self.assertEqual(result.status_code, 303)
            event = client.get("/api/workspace").json()["records"][0]
            self.assertEqual((event["start"], event["end"]), ("2026-11-27", "2026-11-28"))
            self.assertFalse(event["busy"])
            inbox = client.get("/api/outlook/mail")
            self.assertEqual(inbox.json()[0]["subject"], "Room update")
            self.assertNotIn("private body", inbox.text)

    def test_campus_file_sync_removes_old_rows_only_after_success(self):
        timetable = Path(self.temp.name) / "timetable.csv"
        self.config.camu_file = timetable
        timetable.write_text("kind,title,course,start,end,category,external_id\nevent,DBMS,CSE245,2026-11-26T09:00,2026-11-26T10:00,class,c1\n")
        with self.client() as client:
            self.assertFalse(client.post("/api/connections/camu/sync").json()["error"])
            records = client.get("/api/workspace").json()["records"]
            self.assertEqual(records[0]["source"], "camu-feed")
            self.assertEqual(records[0]["start"], "2026-11-26T03:30:00.000+00:00")
            timetable.write_text("invalid headers\n")
            self.assertTrue(client.post("/api/connections/camu/sync").json()["error"])
            self.assertEqual(client.get("/api/workspace").json()["records"], records)
            timetable.write_text("kind,title\n")
            self.assertFalse(client.post("/api/connections/camu/sync").json()["error"])
            self.assertFalse(client.get("/api/workspace").json()["records"])

    def test_bennett_feed_rejects_redirects_and_preserves_calendar(self):
        self.config.bennett_url = "https://lms.bennett.edu.in/calendar/export_execute.php?authtoken=fixture"
        start = (date.today() + timedelta(days=1)).strftime("%Y%m%d")
        calendar = ("BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\nUID:fixture\r\n"
                    f"DTSTART;VALUE=DATE:{start}\r\nSUMMARY:An assignment\r\nEND:VEVENT\r\nEND:VCALENDAR\r\n")
        broken = False
        def handler(request):
            if broken:
                return httpx.Response(302, headers={"Location": "https://example.test/redirect"})
            self.assertEqual(request.url.host, "lms.bennett.edu.in")
            self.assertEqual(request.url.params["authtoken"], "fixture")
            return httpx.Response(200, text=calendar)

        with self.client(httpx.MockTransport(handler)) as client:
            self.assertFalse(client.post("/api/connections/bennett/sync").json()["error"])
            record = client.get("/api/workspace").json()["records"][0]
            self.assertEqual(record["category"], "assignment")
            broken = True
            self.assertTrue(client.post("/api/connections/bennett/sync").json()["error"])
            self.assertEqual(client.get("/api/workspace").json()["records"][0], record)
            self.assertNotIn("authtoken", client.get("/api/workspace").text)

    def test_ics_recurrence_respects_exceptions_and_dst(self):
        content = b"""BEGIN:VCALENDAR\r
VERSION:2.0\r
BEGIN:VEVENT\r
UID:dst-class\r
DTSTART;TZID=America/New_York:20260301T090000\r
DTEND;TZID=America/New_York:20260301T100000\r
RRULE:FREQ=WEEKLY;COUNT=3\r
EXDATE;TZID=America/New_York:20260308T090000\r
SUMMARY:Data structures\r
END:VEVENT\r
END:VCALENDAR\r
"""
        result = parse_ics(content, ZoneInfo("America/New_York"), "camu", date(2026, 3, 1))
        self.assertEqual([record.start for record in result.values()], [
            "2026-03-01T14:00:00.000+00:00", "2026-03-15T13:00:00.000+00:00",
        ])

    def test_manual_dates_are_canonical_and_end_is_exclusive(self):
        record = Record(kind="event", title="Class", start="2026-11-27T12:00:00+05:30",
                        end="2026-11-27T12:00:00+04:30")
        self.assertEqual(record.start, "2026-11-27T06:30:00.000+00:00")
        self.assertEqual(record.end, "2026-11-27T07:30:00.000+00:00")
