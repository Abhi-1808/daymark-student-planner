# Daymark

Daymark is a personal student planner. It brings your timetable, assignments, exams, and study time into one workspace so you can decide what to do next.

## Why build Daymark?

A class can be in MyCamu, a deadline in Bennett LMS, and a study session in Google Calendar. The hard part is working out what still fits after all three are accounted for. Daymark puts the schedule and tasks side by side, shows the time left in your day, and lets you preview a study plan before adding it.

## How do I run it?

Install Git, Python 3.11 or newer, and Node.js 22.12 or newer with npm. Then run:

```bash
git clone https://github.com/Abhi-1808/daymark-student-planner.git
cd daymark-student-planner
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
npm --prefix frontend ci
npm --prefix frontend run build
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In Windows PowerShell, use `py -3 -m venv .venv` to create the environment. Skip the `source` line and use `./.venv/Scripts/python.exe` in place of `python` in the install and launch commands.

Open [http://localhost:8000](http://localhost:8000) and choose **Load sample data** to explore without connecting accounts. Use **New** for your first class or task. You can remove the sample records in Settings.

## How do I plan my day?

| I want to… | Where to go |
| --- | --- |
| See what is next | **Today** shows your schedule, tasks, and remaining free time. Select a date in the week strip to open its agenda. |
| Manage classes and exams | **Calendar** has month, week, and day views. Add recurring events and filter by source or type. |
| Capture an assignment quickly | **New → Quick Add** understands phrases such as `Review SQL tomorrow at 4 pm for 45m p1`. Review the draft before saving it. |
| Find time to study | **Study** shows available slots and timetable conflicts. Set your planning hours and travel buffer in Settings, then preview blocks before adding them. |
| Prepare for an exam | **Study → Exam prep** creates a revision timetable from an exam date, topics, and time estimates. |
| Track subjects and attendance | Open the appropriate tab in **Study** to save notes, record check-ins, and estimate attendance against your target. |
| Find an existing record | Open Search or press **Ctrl+K** or **⌘K** to search events, tasks, and subjects. |

## How do I bring in my timetable?

| Source | How it connects |
| --- | --- |
| Google Calendar and Tasks | Register a Google OAuth web app, then connect it in Settings to read your calendars and task lists. |
| Microsoft Outlook | Register a Microsoft Entra web app for read-only calendar sync. Optional inbox headers let you turn selected messages into local tasks. |
| Bennett LMS | Import an ICS export or configure your own LMS calendar subscription link for scheduled sync. The feed contains the events your LMS calendar makes available. |
| MyCamu | Import an authorized ICS file or use the Daymark CSV template. Scheduled refresh can follow a timetable file on the device running Daymark. |
| Other sources | Import ICS or CSV in Settings, or export a spreadsheet-friendly CSV. |

Provider registration, campus exports, CSV examples, and private phone access are covered in the [setup guide](docs/setup.md). Account consent and live feed availability depend on the provider and your institution.

## Why keep the data local?

Daymark is a single-user workspace. FastAPI serves both the interface and the API from one origin, and SQLite stores your records in one place. The default server listens only on your device. For phone access, set up a private HTTPS route and a workspace password. Keep `.env`, the SQLite database, and timetable exports private. The server encrypts OAuth tokens using `DAYMARK_TOKEN_KEY`.

Imports are read-only. If MyCamu and Google appear to describe the same class, **Review duplicates** lets you hide the Google copy inside Daymark and restore it later. The source calendars keep their original records.

## Why use frosted panels and a Flutter client?

The cobalt and graphite palettes give the schedule some character without changing what needs your attention. Blur is limited to the navigation bars, and the scrolling calendar and task rows use lightweight surfaces. The calendar indexes entries by day and reuses date formatters so switching views does less work. Choose **System**, **Light**, or **Dark** in Settings, or use the moon or sun button.

The Android Flutter client opens the same React and Tailwind interface in a WebView, so the planner has one set of screens and one data model. It connects to your existing Daymark server over HTTPS. For setup, device builds, and browser handoffs for provider consent, see the [Android guide](mobile/README.md).

Daymark uses Calibri where available and bundles [Carlito](https://github.com/googlefonts/carlito) as the fallback. See its [font licence](docs/Carlito-LICENSE.txt).

## What works offline?

A supported browser can reopen the last loaded workspace after the app has been loaded online. The service worker caches the app files, and the browser stores a separate read-only snapshot of your planner. Edits and sync need a connection to the server. Reminders use browser notifications while Daymark is open. Signing out of a password-protected workspace clears the browser snapshot.

## How do I develop and test it?

The FastAPI backend is in `backend/`, the React and Tailwind interface is in `frontend/`, and the Flutter Android client is in `mobile/`.

```bash
npm --prefix frontend test
python -m unittest discover -s tests -p 'test_api.py' -v
npm --prefix frontend run build
python -m pip install -r requirements-dev.txt
python -m playwright install chromium
python tests/browser_smoke.py
```

The browser smoke suite uses a temporary database to exercise desktop and mobile workflows, theme switching, imports, and offline reloads. Set `DAYMARK_CHROMIUM` to use an existing Chromium executable. Provider tests use fixtures, so they can check sync without campus or personal accounts.

For hot reload, start the backend with `DAYMARK_ORIGIN=http://localhost:5173`, then run `npm --prefix frontend run dev` in a second terminal and open [http://localhost:5173](http://localhost:5173). Use the production build to test install and offline behavior.

From `mobile/`, run `flutter pub get`, `flutter analyze`, and `flutter test`. Use `flutter build apk --debug --target-platform android-arm64` to build a test APK with the Android SDK installed.
