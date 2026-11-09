# Project structure

```text
Daymark/
|-- Backend/
|   |-- connectors/          # Google, LMS and MyCamu integrations
|   |-- tests/               # Backend regression tests with fixture data
|   |-- main.py              # FastAPI app, routes and startup lifecycle
|   |-- database.py          # SQLAlchemy engine and sessions
|   |-- runtime.py           # Process ownership, JSON logging and readiness
|   |-- private_access.py    # Loopback and personal Tailscale access checks
|   |-- frontend.py          # Compiled frontend on the API's origin
|   |-- session_queries.py   # Bounded block windows and compact reservation totals
|   |-- security_headers.py  # Shared headers and hashed API-doc initializers
|   |-- models.py            # Calendar, work session and study models
|   |-- duplicates.py        # Matching, review and reversible hiding
|   |-- study.py             # Availability and revision planning
|   |-- study_routes.py      # Subjects, attendance and exam endpoints
|   |-- sync.py              # Shared manual/background sync coordinator
|   `-- scheduler.py         # Five-minute background scheduler
|-- Frontend/
|   |-- public/              # App manifest, icon and service worker
|   |-- scripts/             # Isolated browser QA
|   |-- src/
|   |   |-- app/             # App state and page composition
|   |   |-- components/      # Shared item dialog, loading and offline UI
|   |   |-- config/          # Source names, colors and priority labels
|   |   |-- features/
|   |   |   |-- calendar/    # Day/week views and source visibility
|   |   |   |-- duplicates/  # Duplicate review dialog
|   |   |   |-- integrations/# Connection cards and sign-in dialogs
|   |   |   |-- study/       # Workload, subjects, attendance and revision UI
|   |   |   `-- tasks/       # Quick Add dialog and language parser
|   |   |-- lib/             # Dates, HTTP, offline storage and planning helpers
|   |   |-- styles/          # Shared application styles
|   |   `-- main.jsx         # App entry point
|   `-- tests/               # Frontend unit tests
|-- docs/                    # Features, API, integrations and GitHub guide
|-- scripts/                 # Public tree and repository checks
|-- .github/                 # CI workflow and pull request template
|-- .env.example             # Backend environment reference without secrets
|-- requirements.txt         # Editable backend dependency ranges
|-- requirements.lock        # Exact runtime versions and artifact hashes
|-- README.md                # Overview and quick start
`-- TODO.md                  # Implemented feature checklist
```

Run `python scripts/repository.py tree` for the complete current public file tree.
The command uses Git's ignore rules and checks filenames before printing. Local
credentials, session files, `.ics` exports, databases, dependencies and build output
remain on disk and are excluded from this tree.

The repository root is the backend working directory, so existing database and
credential paths keep working. The `Backend` and `Frontend` names are retained to
preserve launch commands and Python imports across Windows and Linux.

Feature components stay in their own folders. Shared behavior belongs in `src/lib`,
shared presentation in `src/components`, and application composition in `src/app`.

`app/useWorkspaceView.js` owns navigation, selected dates, display filters, search,
and sidebar/agenda preferences. It derives visible calendar/task lists without
changing imported items. Sync actions, sync-status polling and duplicate review
have their own hooks; `App.jsx` connects those hooks to the page components.

`styles/tokens.css` is loaded before component styles and owns the effective dark
palette, calendar-source colors, native-control color scheme and local font stacks.
Typography uses installed system fonts; no external font download is required.
`workspace.css` and `usability.css` provide layout and tool-specific treatments.

`scripts/run_local.py` starts the compiled frontend and API on one loopback port,
without reload or multiple workers. Its optional `--phone` mode reads the connected
Tailscale account and restricts private HTTPS access to that owner. See
[Android setup](android.md). The build plugin in `Frontend/scripts/pwa-build.js`
versions the service-worker cache from the full public build contents.

`config/security-headers.json` is shared by the backend and Chrome fixture server,
so browser QA exercises the compiled application under its deployed CSP.
`scripts/sync_report.py` aggregates safe failure events from explicitly supplied
local JSON logs. Browser waits share a 15-second deadline, configurable with
`DAYMARK_QA_TIMEOUT_MS` (100–120000 milliseconds), including a deadline for stalled
evaluations. See `CHANGELOG.md` for the v0.3.0 release scope.
