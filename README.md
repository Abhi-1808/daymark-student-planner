# Daymark

A calendar and study planner for Bennett University students. Daymark combines
Google Calendar and Tasks, Bennett LMS deadlines, MyCamu classes and Outlook in one local
workspace, with automatic refreshes and offline viewing.

## In plain terms

Daymark collects your class timetable, your assignment deadlines and your own
to-do list on one screen, then helps you find time to study around your classes.

It runs on your own computer and stores your combined planner locally. It reads
your connected calendars and Outlook email headers without changing those records.

You can also open it on your phone over a private connection, so you can check
your day away from your desk. The computer must stay switched on and awake for
live updates; without it, the app shows the last saved copy.

If you want the story of how the project got here, in everyday language, see
**[What changed, and why](docs/what-changed.md)**. To set it up on an Android
phone, follow **[the phone guide](docs/android.md)**.

**Not yet tested:** the actual installation on a real Android phone, and a run
on GitHub's own test servers. Both need your devices or an uploaded copy — see
the end of the page linked above.

## Features

- Month, day and weekly timetable views with persistent source visibility controls.
- Google, LMS and MyCamu imports refreshed every five minutes while the backend runs.
- Outlook meetings/invitations, explicitly selected email reminders and opt-in device alerts.
- Duplicate detection with review, explicit confirmation and Undo.
- Task priorities, duration estimates, subtasks and study sessions.
- Class conflicts, walking buffers, free-time suggestions and workload warnings.
- Subject notes, useful links and a manual attendance calculator.
- Exam revision previews with explicit confirmation before scheduling.
- Natural-language Quick Add with an editable preview.
- Manual-item CSV export and explicit create-only import with row-level feedback.
- An installable frontend with saved calendar and study data for offline viewing.

Imported calendars remain read-only. Local priorities, notes and study sessions do
not change your institution's records or source calendars.

## Quick start

Use Python 3.10 or newer (3.12 is recommended), Node 22 or newer, and npm.
Run the backend from the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.\.venv\Scripts\python.exe -m uvicorn Backend.main:app --reload
```

On macOS/Linux, use `.venv/bin/python` in place of the Windows Python path.
`requirements.lock` pins the backend's full dependency tree and artifact hashes;
`requirements.txt` remains the editable input. See [dependency updates](docs/dependencies.md)
to regenerate the lock. CI installs the same lock with hash verification.

In a second terminal, start the frontend:

```powershell
Set-Location Frontend
npm ci
npm run dev
```

Open **http://localhost:5173**. The API runs at **http://localhost:8000** and its
interactive reference is at **http://localhost:8000/docs**. Existing Python
installations can keep using `python -m uvicorn Backend.main:app --reload`.

## Connections and settings

For the compiled app on your computer or Android phone, use the
[Android and private access guide](docs/android.md). `python scripts/run_local.py`
serves the built frontend and API together, with one worker and no development
reload. Phone access uses the same personal workspace through private HTTPS.
The backend accepts direct loopback requests by default; private phone requests
require the launcher's `--phone` mode and the configured Tailscale identity.

Open **Settings** to connect Google, MyCamu, Outlook or the live LMS calendar. Sign-in is
completed in the source's browser flow. See [integration setup](docs/integrations.md)
for OAuth files, Microsoft institution login, live LMS subscriptions and reconnecting.
For Classic Outlook setup, the alternative Graph registration and reminder behavior,
see [Outlook setup](docs/outlook.md).

For CSV columns, limits and create-only behavior, see [CSV files](docs/csv.md).
The [team handoff](docs/team/README.md) now follows the original named roles.

[.env.example](.env.example) lists backend settings. It is a reference file; export
the values you need in the terminal that starts the backend. The backend does not
automatically load `.env`. For example, in PowerShell:

```powershell
$env:AUTO_SYNC_INTERVAL_SECONDS = "300"
python -m uvicorn Backend.main:app --reload
```

The compiled app normally uses its own origin; Vite development/preview servers
use their current host on port 8000. To override it, copy
[Frontend/.env.example](Frontend/.env.example) to `Frontend/.env.local`, edit
`VITE_API_URL`, and restart Vite.
Keep that override unset for the compiled single-address app: its security policy
allows API connections to its own origin. Development/preview API overrides remain
available through Vite.

Local OAuth credentials, session files, private calendar subscriptions, databases
and downloaded calendars are ignored by Git. Keep running the backend for automatic
refreshes. Phone access uses a private HTTPS connection to the computer; see the
Android guide above. The computer must remain running for live syncing.

## Project layout

```text
Backend/             FastAPI app, connectors, planning logic and tests
Frontend/src/app/    App state and page composition
Frontend/src/features/  Calendar, tasks, study, duplicates and integrations
Frontend/src/components/  Shared UI components
Frontend/src/lib/    Dates, HTTP, offline storage and planning helpers
Frontend/src/styles/  Application styles
Frontend/public/    Service worker, manifest and icon
docs/               Setup, features, API, architecture and GitHub guide
scripts/            Public project tree and repository filename checks
.github/            Test workflow and pull request template
TODO.md             Implemented feature checklist
```

See the [structure guide](docs/project-structure.md) for folder responsibilities.
See the [v0.3.0 changelog](CHANGELOG.md) for the local operations and Android release.
To print the full public tree without local data or installed dependencies:

```powershell
python scripts/repository.py tree
```

## Local diagnostics and history

Each failed source attempt emits one structured `daymark.sync.failed` event with
its source, classification and status code, without provider messages or tokens.
Save the launcher's JSON stderr to a log file, then summarize the supplied logs:

```powershell
python scripts/sync_report.py path/to/daymark.log --days 7
```

The report counts events present in those files during the trailing seven days;
keep the logs you want included. It is local and does not upload diagnostics.
Study history is kept indefinitely by the current policy. Deleting old blocks would
affect reservation totals, so the date-window API is not an automatic deletion rule.

The compiled app applies security headers from `config/security-headers.json`.
Inline scripts are blocked; inline styles remain allowed for positioned calendar
entries. API documentation has a separate, hashed initializer/CDN policy.

## Verification

From the repository root:

```powershell
python -m unittest discover -s Backend/tests -v
python -m unittest discover -s scripts -p "test_team_handoff.py" -v
python scripts/repository.py check --history
```

From `Frontend`:

```powershell
npm test
npm run build
npm run test:browser
```

Browser QA needs Chrome or Chromium. Set `DAYMARK_CHROME_PATH` if it is outside
its standard location. It uses an isolated browser, a temporary local server and
fixture API responses, so your real calendar and attendance are unchanged.

For Chrome installed in the standard Windows location, run from `Frontend`:

```powershell
$env:DAYMARK_CHROME_PATH = 'C:\Program Files\Google\Chrome\Application\chrome.exe'
npm run build
npm run test:browser
```

If Chrome is installed elsewhere, replace the path with its `chrome.exe` location.
The backend does not need to be running for these browser checks.

## Documentation

- [Using the calendar and study tools](docs/features.md)
- [Integration setup and syncing](docs/integrations.md)
- [API reference](docs/api.md)
- [Project structure](docs/project-structure.md)
- [GitHub preparation](docs/github.md)
- [Feature checklist](TODO.md)
- [Five-person team modules and shareable packages](docs/team/README.md)

GitHub preparation is local. No remote or publication is needed to use Daymark.
