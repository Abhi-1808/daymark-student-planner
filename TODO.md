# Daymark feature checklist

## Milestone 1 parity — 7 November 2026

- [x] Share overlap and short room-change detection in a pure Python function.
- [x] Check manual event saves before writing and require an explicit override for intentional overlaps.
- [x] Use Python conflict results in Study, with labelled saved checks offline.
- [x] Add create-only CSV import/export with Python file handling, limits and row-level feedback.
- [x] Remap team handoffs to the original Input, Slots, Output, Testing and Integration roles.


All ten researched suggestions were implemented in dependency order and verified
on 27 October 2026. Browser checks use fixture data and preserve real imports.

- [x] 1. Source visibility controls — persistent display preferences; never delete imported events.
- [x] 2. Full weekly timetable — classes, deadlines, study sessions, navigation and day drill-down.
- [x] 3. Conflict detection and configurable walking time — exclude matching imported copies from conflict warnings.
- [x] 4. “What can I finish now?” — rank pending tasks by available time, deadline and priority.
- [x] 5. Weekly workload meter — compare remaining estimated work with real free study time.
- [x] 6. Subject pages — group classes and deadlines; save personal notes and useful links.
- [x] 7. Attendance calculator — persistent manual counts, a user-selected target and future scenarios.
- [x] 8. Exam preparation planner — topics, realistic available slots, preview and explicit confirmation.
- [x] 9. Natural-language quick add — parse dates/times and preview before creating a local task.
- [x] 10. Installable app and offline viewing — cache the last successful timetable, label stale data and reconnect safely.

## Audit fixes — 30 October 2026

- [x] Keep task filters separate from calendar navigation and preserve deliberate calendar filters.
- [x] Normalize item/session timestamps and session-date filters to campus time before validation or database comparisons.
- [x] Keep five-minute breaks around saved sessions and across midnight when allocating new blocks.
- [x] Batch duplicate-preview keeper lookups while preserving every hidden copy and review choice.
- [x] Require a task when creating a study session; reject event and missing IDs.
- [x] Extract the month calendar and index events across every occupied day, excluding their ending midnight.
- [x] Restrict revision queries to their planning horizon and prepare busy intervals once, preserving stale-preview checks.

## Follow-up audit checks — 30 October 2026

- [x] Verify controlled manual/background sync failures and sanitized diagnostics; report malformed LMS calendars as provider errors.
- [x] Share dialog focus trapping, focus return, Escape handling and nested scroll locking across all five modals.
- [x] Share the aligned planning-start helper, preserving a full five-minute preview review window.
- [x] Reuse the shared local date key across calendar views and study helpers.
- [x] Verify the existing safe study-preference fallback with empty, partial, invalid and blocked-storage regressions.
- [x] Move model-derived additive schema upgrades into application startup; importing the app leaves the database untouched.
- [x] Test the mounted React sync hook's visibility, API changes, cancellation and unmount cleanup.
- [x] Use validated ItemSource members for connector sources while preserving opaque provider record IDs.

## CI and App structure — 30 October 2026

- [x] Verify released action versions and pin their exact commits on Ubuntu 24.04.
- [x] Name CI stages and document the standard-library repository check and build-before-browser ordering.
- [x] Extract sync and duplicate-review state/actions from App into dedicated hooks with cancellation and explicit-review safeguards.
- [x] Add mounted React checks for sync actions, duplicate preview races, confirmation and Undo.

## Workspace view extraction — 31 October 2026

- [x] Move navigation, selected dates, display filters, search and workspace preferences into `useWorkspaceView`.
- [x] Keep task/calendar filters independent and memoize visible lists, search suggestions and the pending-task count.
- [x] Verify navigation, search, immutable inputs, StrictMode remounts and blocked-storage fallbacks with the real mounted hook.
- [x] Re-run 48 frontend tests, 4 packaging checks, the production build and the complete Chrome suite.
- [x] Document the Windows Chrome path and all three test-suite commands in the README.

`App.jsx` now has 196 lines and 14 direct state hooks. Backend code is unchanged
by this extraction; browser scenario groups remain separate from the core test count.

## Palette cleanup and hidden-source search — 31 October 2026

- [x] Consolidate the effective palette and local font stacks in `styles/tokens.css`, preserving source colors and native dark controls.
- [x] Remove competing root palettes, obsolete font references and 475 provably shadowed legacy declarations.
- [x] Verify computed fonts, colors and layouts against the pre-edit CSS in 14 clean-browser screen/layout comparisons.
- [x] Test hidden-source search in the mounted hook and actual UI without changing source visibility or removing copies.
- [x] Preserve the duplicate-review opener while loading, then restore keyboard focus when its dialog closes.
- [x] Pass 48 frontend tests, 4 packaging checks, the production build and the full browser suite.

The compiled CSS is 77.90 kB (16.14 kB gzip), down from 89.38 kB (18.39 kB gzip).

## QA and handoff hardening — 31 October 2026

- [x] Describe the package baseline as the current public working tree, with the actual HEAD recorded in each archive's manifest and guides.
- [x] Reject baseline recording for zero or multiple emitted CSS files, including nested lazy chunks; replace only the mapped stylesheet.
- [x] Run palette and typography checks at every tested responsive width for week, day, subjects, attendance, exams and the Today planner.
- [x] Verify the added filesystem guards and package baseline stamps; pass 51 frontend tests, 4 packaging checks, the production build and full Chrome suite.

## Constraints

- Keep Google, LMS and MyCamu imports read-only.
- Keep the presentation duplicates; removing copies always requires explicit review.
- Hidden sources remain busy time for planning and workload calculations.
- Attendance starts with manual counts; calendar events do not prove attendance.
- An installable frontend does not make a laptop backend reachable from a phone.
- Offline viewing must never cache authentication responses or replay calendar writes.

## Verification

- Suite counts: 185 backend tests, 65 frontend tests and 4 team-handoff checks.
- That is 250 core tests plus 4 packaging tests, or 254 total; builds and browser scenarios are separate checks.
- Production build passes.
- `npm run test:browser` starts an isolated local server and Chrome, then checks
  weekly views, source persistence, conflicts, task suggestions, subject notes,
  attendance scenarios, exam preview/confirmation, Quick Add and offline reloads.
- Browser checks cover 320, 375, 768 and 1440 pixel layouts.
- Regression checks cover Tasks → Today → day schedule, preserved calendar filters, and multi-day month events.
- Browser checks also mount the real sync hook and shared dialogs, exercising visibility, cancellation, StrictMode cleanup, nested focus trapping and Create-menu focus return.
- Real Google Calendar, Google Tasks, LMS and MyCamu sync remains enabled.
- Presentation duplicate removal remains a separate explicit review action.

## Deployment follow-up

Current direction: one personal workspace, with an Android install using a private
connection to the computer. A hosted multi-user service has not been selected.
Attendance still uses manual counts, not an unverified portal import.

## Personal Android preparation — 31 October 2026

- [x] Serve the compiled app and API from one address using `scripts/run_local.py`.
- [x] Keep desktop dev/preview API defaults while using same-origin requests on the phone.
- [x] Accept direct loopback traffic or one configured Tailscale owner/host; reject direct network access, other users, cross-origin requests and leftover unconfigured proxy mappings.
- [x] Read phone settings from the connected computer's Tailscale account with `--phone`; leave network publication as a separate explicit Serve command.
- [x] Keep source sign-ins on the computer and block phone requests from launching its browser.
- [x] Add 192px/512px Android PNG icons rendered from the existing SVG and check Chrome installability.
- [x] Version the service-worker cache from all public build contents; preserve saved data and exclude API/auth responses.
- [x] Use SQLite WAL and a five-second busy timeout, holding a DB-specific OS lock until the scheduler shuts down.
- [x] Add a database/scheduler readiness check, JSON logs and request IDs without logging query strings.
- [x] Verify private access, compiled assets and sign-in restrictions over real HTTP with an isolated temporary database.
- [ ] Connect Tailscale on the actual computer and phone, then verify Android installation and reconnect. User chose to connect devices later; follow `docs/android.md`.

## Further operational work

- [x] Lock runtime dependencies and artifacts with hashes; verify clean installs on CPython 3.10 and 3.12 and make CI/setup/handoffs use the lock.
- [x] Restrict daily-planner reads to selected tasks, their reservations and padded conflicts inside a fixed preview window, with indexes added safely for existing work-session tables.
- [x] Bound the sessions API and frontend transport with explicit date windows, preserving historical navigation and compact reservation totals.
- [x] Keep study history indefinitely by explicit user choice on 1 November 2026. Date windows limit transport, not storage; old reservations must keep contributing to task totals.
- [ ] Add explicit backup/restore tooling and versioned schema migrations before destructive schema changes.
- [ ] Standardize provider time budgets and retry/backoff rules.
- [ ] Add measured accessibility checks and a privacy-conscious browser error-reporting design.
- [x] Emit one structured failure event per failed attempt and aggregate supplied local logs with `scripts/sync_report.py`.
- [ ] Evaluate crash aggregation or durable metrics if operational needs grow beyond saved local logs.
- [ ] Push only when requested, then verify the real GitHub-hosted CI run.
- [ ] If hosting is selected later, design user accounts, data isolation, per-user credentials and deployment artifacts first.

IndexedDB snapshots already replace the value for each API origin and data kind;
they do not append a new copy on every sync. Server-side historical payload growth
is a separate follow-up. The earlier CSS-chunk guard and responsive style checks
are already implemented; the remaining QA key mapping now rejects unsupported keys.

## Lockfile and audit verification — 31 October 2026

- [x] Add `requirements.lock` with exact transitive versions, platform markers and SHA-256 hashes, retaining the already-tested runtime versions.
- [x] Enforce `--require-hashes --only-binary=:all:` in setup, CI and team handoffs, with CI's pip cache keyed on the lock and a dependency-consistency check.
- [x] Verify that importing the app leaves its OS lock free, lifespan holds it, and normal shutdown or failed startup releases it. The lock was already lifecycle-bound; no move was necessary.
- [x] Re-run the existing zero/single/multiple CSS-chunk regression checks. Baseline recording already fails closed for split chunks.
- [x] Preserve planner results while skipping unrelated history; test padded boundaries, midnight breaks, selected-task reservations and stale-preview invalidation.
- [ ] Complete a week of actual Android use after device connection, including laptop sleep, network loss and reconnect. This remains a manual device trial.

## Windowed session transport — 31 October 2026

- [x] Default `/api/sessions` to the previous 90 days, today and the next 90 days; support explicit historical bounds with a maximum 366-day span.
- [x] Include overlapping blocks across window boundaries, normalize offsets to campus time, order ties by ID and reject invalid/overflowing windows.
- [x] Make every frontend session request include both bounds and reload when the selected dates need a different window.
- [x] Record offline window coverage, trim cached rows to the requested range, warn on missing coverage and reject stale in-flight window responses.
- [x] Keep Today planner reservations correct with compact full-history totals on the item list, using SQL aggregation and two queries for the entire list.
- [x] Verify whole-minute and microsecond boundaries, historical navigation, explicit-window transport and preservation of all stored rows.
- [x] Pass 175 backend tests, 60 frontend tests, four packaging tests, the production build and the complete Chrome suite.

The status poll runs every ten seconds, but it reloads items/sessions only after a
source completion changes, a previous refresh failed, or the initial load. UI
mutations, reconnect and date-window changes also trigger bounded data refreshes.

## Operations release — 1 November 2026

- [x] Retain all study history as requested; no pruning or archive job is enabled.
- [x] Resolve the Windows Tailscale CLI only from its absolute standard installation directory, rejecting PATH shims and relative install roots.
- [x] Share production security headers with Chrome QA: restrict app scripts/API origins, block frames and device permissions, and suppress referrers.
- [x] Keep API docs usable with scoped CDN permissions and initializer hashes instead of arbitrary inline scripts.
- [x] Apply headers and request IDs to controlled unexpected errors as well as successful, rejected and missing routes.
- [x] Record safe sync-failure classifications and summarize saved logs over a bounded reporting period.
- [x] Replace fixed four-second browser polling with a shared 15-second overall deadline, configurable up to 120 seconds, including stalled evaluations and cleanup.
- [x] Pass 183 backend tests, 65 frontend tests, four handoff tests, the production build and Chrome QA under the deployed security policy.
- [x] Prepare the v0.3.0 version metadata and changelog for a local release marker.
- [ ] Complete GitHub-hosted CI after a repository/push is requested, and complete the deferred Android trial on real devices.

## Operational feedback follow-up — 1 November 2026

- [x] Re-check the clean v0.3.0 tree before editing; all four hardening items are already present.
- [x] Log the absolute Tailscale executable path with a stable event, excluding CLI status contents and making no signature-verification claim.
- [x] Keep study history, sanitized sync exceptions and the existing CSP/wait behavior intact.
- [ ] Hosted GitHub Actions and the real-phone trial remain unverified; local checks are reported separately.

## Outlook integration — 4 November 2026

- [x] Add Microsoft public-client sign-in, read-only calendar/email-header imports and five-minute scheduled refreshes.
- [x] Show pending calendar invitations, an explicit email reminder picker and opt-in device alerts.
- [x] Preserve study history, local reminder editability and private-token/package exclusions.
- [x] Add a Windows Classic Outlook reader for the signed-in Bennett profile, bounded metadata, offline-cache status and explicit native item opening.
- [x] Pass 215 backend tests, 77 frontend tests, four packaging tests, the production build and the full isolated Chrome suite including the desktop flow.
- [x] Verify live Classic Outlook connection and automatic sync: 2 calendar entries, 50 recent inbox headers and 2 meeting-request emails on 4 November 2026. No live reminder was created.
- [ ] Optional Graph mode still needs Bennett administrator approval; the first direct sign-in reached Microsoft's approval-required screen. Classic mode does not grant Graph access.
- [ ] Verify real Android notification delivery separately from the mocked Chrome notification checks.
