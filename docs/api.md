# API reference

Direct API access is restricted to loopback. Personal phone access requires the
configured Tailscale Serve identity and HTTPS host; see [Android setup](android.md).
Rejected requests return 403. API responses use `Cache-Control: no-store` and
carry an `X-Request-ID` for local diagnostics.
The compiled frontend and API responses also receive the shared CSP, referrer,
permissions and frame headers. Unexpected failures return a generic 500 with a
request ID; detailed exception text is excluded from structured logs. `/docs` and
`/redoc` allow their documentation CDN assets and hashed initialization code while
the app's script policy remains restricted to its own origin.

`GET /health` probes database readability and the expected sync scheduler/job,
returning 200 with `status`, `database` and `scheduler`, or 503 if unavailable.
Deliberately disabled automatic sync is healthy. Provider failures are reported
separately by `/api/sync/status`; the health probe never contacts providers.

- `GET /health`
- `GET /api/google/status`
- `GET /api/google/login` to start read-only Google OAuth
- `GET /api/integrations/status` for connection status without secrets
- `GET /api/items` with optional `type`, `status`, and `source` filters
- `GET /api/items/{id}`
- `GET /api/items/export.csv` for a manual-item CSV attachment
- `POST /api/items/import` with a raw UTF-8 `text/csv` file body; see [CSV format and limits](csv.md)
- `GET /api/conflicts?from=...&to=...&walking_minutes=10` for Python timetable checks in a window of at most 93 days
- `POST /api/items` for manual events and tasks
- `PATCH /api/items/{id}` for manual items
- `PATCH /api/items/{id}/priority` to set a local priority override on any item
- `PATCH /api/items/{id}/status` to complete or reopen a task locally
- `DELETE /api/items/{id}` for manual items
- `GET /api/sessions` with optional `from_date` and exclusive `to_date` to list overlapping study blocks in a bounded window
- `POST /api/sessions` to add a study block for an existing task
- `POST /api/sync/google_cal` to import Google Calendar events
- `POST /api/sync/google_tasks` to import Google Tasks
- `POST /api/sync/lms` to import an LMS iCal feed
- `GET /api/camu/status` for MyCamu connection status
- `POST /api/camu/microsoft/start` to open institution sign-in locally
- `GET /api/camu/microsoft/{attempt_id}` to wait for Microsoft sign-in
- `DELETE /api/camu/microsoft/{attempt_id}` to cancel that sign-in
- `POST /api/camu/login` to sign in to MyCamu
- `POST /api/camu/otp/request` and `POST /api/camu/otp/verify` for verification codes
- `DELETE /api/camu/session` to disconnect MyCamu locally
- `POST /api/sync/camo` to import the MyCamu timetable
- `GET /api/sync/status` for background refresh status
- `GET /api/lms/status` for live subscription status
- `POST /api/lms/connect/start` to open a one-time LMS sign-in window locally
- `GET /api/lms/connect/{attempt_id}` to wait for live calendar connection
- `DELETE /api/lms/connect/{attempt_id}` to cancel the sign-in
- `POST /api/sync` to refresh all configured sources
- `GET /api/duplicates` to preview similar MyCamu and Google Calendar events
- `POST /api/duplicates/remove` to remove explicitly confirmed local copies
- `POST /api/duplicates/restore` to undo approved duplicate removals

Events require `start`; tasks require `due`. Imported items will remain
read-only for their title, dates, and source fields, preserving the one-way
import boundary. Their priority can be changed locally in Daymark for planning
and color-coding without writing anything back to the source service.
When a task is first created or imported, Daymark starts with high priority
when it is due within two days, medium priority within seven days, and low
priority later than that. Changing the priority creates a local override that
future syncs preserve.

Manual event creation and editing check overlapping timed events before writing.
A rejected save returns HTTP 409 with `detail.code = "event_conflict"`, a readable
message, conflict records (`type`, event IDs `a`/`b`, `minutes`) and the existing
event details. No draft changes are persisted. The editor offers a separate
**Save anyway** action, which sends the strict boolean `allow_conflict: true`.
This request-only field is never stored and does not bypass imported read-only
protection. Task saves, point events and midnight-to-midnight all-day entries do
not trigger this timed-class warning.

Save-time validation deliberately uses a zero-minute walking buffer: only a
timed overlap requires confirmation. Study uses the chosen walking buffer
(10 minutes by default) to also advise about short room changes. A five-minute
room change can therefore appear in Study while the event saves normally.

`GET /api/conflicts` uses the same pure Python engine for overlap and short
room-change warnings. Its `from`/`to` bounds use campus time, the end is exclusive,
and `walking_minutes` is an integer from 0 to 60. Matching Google/MyCamu imports
count once for analysis; no copies are removed. Study caches each week's checks
for offline viewing, marks cached results as saved, and does not claim a clean
timetable when a check fails without a saved result.

Item and study-session `start`, `end`, and `due` values use campus time
(Asia/Kolkata). Offset-bearing input is converted to campus time before range
validation and storage; input without an offset already represents campus time.
These schedule values are returned without an offset; both session-window bounds
follow the same convention. Study blocks require a task ID: an event ID
is rejected with HTTP 400, and a missing ID with HTTP 404.

## Session window contract

`GET /api/sessions` always has two date bounds. With neither parameter, the window
starts at campus midnight 90 days ago and ends at midnight 91 days ahead: today,
the previous 90 days, and the next 90 days. It does not return all stored history
or arbitrarily distant future sessions.

- `from_date` alone starts an explicit 90-day window at that timestamp.
- `to_date` alone returns the 90 days preceding that timestamp.
- With both parameters, the requested span must be positive and at most 366 days.
- Results overlap `[from_date, to_date)`: a block ending exactly at the start or
  starting exactly at the end is excluded; a block spanning the start is included.
- Results are ordered by start, then ID. Invalid, reversed, oversized or overflowing
  ranges return 422. No rows are deleted by these reads.

For example, retrieve historical blocks using
`/api/sessions?from_date=2024-01-01T00:00:00&to_date=2024-02-01T00:00:00`.
Request successive windows for a longer history. `from_date` now denotes an overlap
boundary rather than excluding a block merely because it started earlier.

`GET /api/items` also provides read-only `reserved_minutes` totals across each
item's full session history. Positive blocks are floored to whole minutes before
summing, matching the daily planner. The server aggregates these totals in SQL,
using one additional query for the whole item list; it does not load or transfer
every historical session. Other item responses may leave this computed field null.

The frontend requests a five-month window around the relevant dates: two complete
months before the selected month, the selected month, and two months after it.
Day/week/Study views use their selected day; Today, Tasks, Profile and the month
calendar use today. The month calendar displays imported/manual items rather than
study blocks. Navigating to a distant day/week requests a new bounded window.

Offline snapshots record which session window they cover. For dates outside that
coverage, the interface warns that saved study blocks may be incomplete and keeps
writes disabled. Delayed responses for a previous window cannot replace the
currently requested schedule. Today uses the compact full-history reservation
totals to avoid treating previously reserved work as unscheduled.

Tasks also support `priority`: `low`, `medium`, or `high`. The Tasks view in
the frontend lists every task and can filter by priority or sort by earliest
due date.

The SQLite location defaults to `calendar_tasks.db`. Set `DATABASE_URL` to use
another database, such as PostgreSQL, without changing application code.

Schema setup and supported legacy-column upgrades run in the application's
startup lifespan. Importing `Backend.main` does not open or modify the database;
integration tests that exercise startup should enter the app lifespan explicitly.


## Study planning

- `POST /api/schedule/plan` with `task_ids`, `start_hour`, `end_hour` and
  `buffer_minutes` previews selected unfinished tasks for today. Returns proposed
  sessions, reasons for work that does not fit, a `token` and `expires_at`.
- `POST /api/schedule/auto` requires `{ "token": "...", "confirmed": true }`.
  It saves exactly the reviewed daily preview as study blocks, once. A stale,
  expired or already consumed token is rejected with HTTP 409. Previewing does not
  create sessions. This replaces the previous immediate scheduling request.
- `GET /api/study/subjects`
- `PUT /api/study/subjects/{key}`
- `GET /api/study/exams`
- `POST /api/study/exams`
- `POST /api/study/exams/{id}/preview`
- `POST /api/study/exams/{id}/plan`

Both planners leave at least five minutes to review a preview, then align its
earliest possible slot to a five-minute boundary. Planning leaves a five-minute
break next to existing study blocks as well as
between newly proposed blocks. Revision previews check conflicts within their
planning horizon, and confirmation rejects a preview when relevant calendar
events, saved study blocks, or the exam change.

See `/docs` on the running backend for request schemas and response models.
