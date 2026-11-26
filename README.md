# Daymark

A personal student planner for Bennett University and other college workflows. See your classes, assignments, exams, and study time together. Daymark runs on your own device and stores the workspace in SQLite.

## Run locally

You need **Python 3.11 or newer**, **Node.js 22.12 or newer**, and npm.

From the repository root, build the frontend and start the server.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

On Windows PowerShell, use `py -3 -m venv .venv` to create the environment, then use `./.venv/Scripts/python.exe` in place of `python` in the install and launch commands. Skip the `source` line.

Open **[http://localhost:8000](http://localhost:8000)**. Choose **Load sample data** to explore or select **Create** to start with your own timetable. Sample records can be removed from Settings.

## What you can do

| Area | Workflow |
| --- | --- |
| Today | See your schedule, tasks due, and remaining free time. Open a day directly from the week strip. |
| Calendar | Switch between month, week, and day. Add recurring classes, holidays, exams, or personal events. Filter by type or source. |
| Tasks | Set deadlines, priorities, estimates, recurrence, and optional reminders. Tick off individual occurrences. |
| Study | Find free slots, check timetable clashes and room-change buffers, and preview study blocks before adding them. |
| Subjects and attendance | Group tasks and classes by subject code. Save subject notes, record attendance, and preview your percentage against a target. |
| Exam prep | Pick an exam date, enter topics and estimates, and preview a revision timetable. |
| Quick Add and search | Try `Review SQL tomorrow at 4 pm for 45m p1`. Use Ctrl+K or ⌘K to find records across sources. |
| Appearance and offline | Choose System, Light, or Dark. Install Daymark from a supported browser and reopen the last loaded workspace offline. |

Calibri is used when it is installed. The app bundles [Carlito](https://github.com/googlefonts/carlito) as the fallback. Its [font licence](docs/Carlito-LICENSE.txt) is included.

## Bring in your calendars

| Source | Setup |
| --- | --- |
| Google Calendar and Google Tasks | Register a Google OAuth web app and connect in Settings. Reads calendars and task lists your account can access. |
| Microsoft Outlook | Register a Microsoft Entra OAuth web app and connect in Settings. Calendar access is read-only. Optionally enable inbox headers so you can turn selected messages into local tasks. |
| Bennett LMS | Import an ICS file or configure your own LMS calendar subscription link for scheduled sync. The feed shows what the LMS exposes on its calendar. |
| MyCamu | Import an ICS or Daymark-format CSV timetable. You can configure Daymark to refresh from a local file when you update it. |
| Other data | Import ICS or CSV from Settings. Export a spreadsheet-friendly CSV for review. |

See [provider setup, import examples, and private phone access](docs/setup.md). Google, Outlook, and Bennett protocol flows are covered by fixture tests. Real account consent and Bennett feed availability depend on the registrations and export options available to your account.

## Persistence and privacy

- The instance belongs to one person. The default server binds to loopback. For private phone access, configure an HTTPS origin, a workspace password, and a private network route.
- Keep `.env`, the database, and any provider exports private. OAuth tokens are encrypted with `DAYMARK_TOKEN_KEY`.
- **Review duplicates** hides your selected Google Calendar copies in Daymark. The source calendars remain untouched. Restore a copy from the same review window.
- The service worker caches app files. The browser separately keeps the last loaded workspace for offline reading. Signing out of a password-protected workspace clears that browser snapshot.
- Device reminders use browser notifications while Daymark is open. Calendar and task sync runs while the backend is running.

## Develop and verify

The FastAPI app lives in `backend/`, the React/Vite client in `frontend/`, and regression checks in `tests/`. The production server serves both the frontend and API from one origin.

```bash
npm --prefix frontend test
python -m unittest discover -s tests -p 'test_api.py' -v
npm --prefix frontend run build
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tests/browser_smoke.py
```

Use `DAYMARK_CHROMIUM` to run the smoke test against an existing Chromium executable. Tests use temporary databases and fixtures.

For frontend hot reload, run the backend with `DAYMARK_ORIGIN=http://localhost:5173`, then run `npm --prefix frontend run dev` in a second terminal and open [http://localhost:5173](http://localhost:5173). The installable and offline flows use the production build.
