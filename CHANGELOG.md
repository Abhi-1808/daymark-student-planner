# Changelog

## Unreleased

- Add bounded manual-item CSV export/import with shared validation, row-level
  errors, create-only persistence and explicit confirmation in Settings.
- Align team packages with Suraj/Input, Rishabh/Slots, Ayush/Output,
  Atulaya/Testing and the Integration role.

- Share timetable overlap and room-change warnings in Python. Check manual event
  saves before writing, offer explicit Save anyway, and show the same results in
  Study with labelled saved checks offline.

- Support the signed-in Bennett account in Classic Outlook on Windows as an
  alternative to Graph consent. Read bounded local calendar/inbox metadata,
  surface request emails, and open native Outlook items only when selected.

- Add Outlook calendar/invitation syncing, a metadata-only inbox picker, explicitly
  confirmed local email reminders and opt-in browser/service-worker alerts.
- Keep Microsoft credentials out of shared packages; document registration,
  university approval and open-browser notification limits.

- Log the absolute Tailscale executable path before phone setup on every platform,
  without logging its status contents or implying publisher/signature verification.
- Preserve the existing security policy, exception redaction, fail-fast browser
  errors and indefinite study-history policy.

## v0.3.0 — 1 November 2026

### Personal Android access

- Serve the compiled frontend and API from one loopback address with a dedicated
  single-worker launcher and optional private Tailscale access for one owner.
- Keep source sign-ins on the computer. On Windows, resolve Tailscale from its
  standard installation directory rather than accepting a PATH shim.
- Add Android installation icons and a service-worker cache version derived from
  the public build. Save session-window coverage with offline data.

### Operations and security

- Add SQLite WAL/busy handling, a database-specific OS lock held during lifespan,
  database/scheduler readiness probes, structured logs and request IDs.
- Hash-lock the backend dependency tree and use verified, wheel-only installs in
  setup, team handoffs and CI.
- Apply a shared CSP, referrer, permissions and frame policy to the compiled app,
  APIs and errors. API docs use narrowly scoped CDN assets and initializer hashes.
- Emit a safe `daymark.sync.failed` event once per failed attempt and summarize
  saved logs locally with `scripts/sync_report.py`.

### Planning and interface

- Limit session transport and planning reads to relevant dates; preserve full task
  reservation totals through compact SQL aggregation and keep all study history.
- Add session lookup indexes and preserve preview/confirmation checks across
  padded boundaries and midnight.
- Consolidate theme tokens and local fonts, preserve hidden-source search, and
  harden responsive checks and CSS-baseline asset mapping.
- Use a shared, configurable browser wait deadline, including stalled evaluations.
  Run the compiled app under the real security policy during Chrome QA.

### Verification and delivery

Local validation passed 183 backend, 65 frontend and four packaging tests (252
total), the production build and Chrome QA under the shared security policy.

This is a local release marker. GitHub-hosted CI has not run because no remote is
configured. Actual Android installation and a week of device use remain pending.
Study history is retained by explicit user choice; no automatic pruning is enabled.
