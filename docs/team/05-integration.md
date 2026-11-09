# You: Integration and persistence

Assigned review and development role: **You**. This follows the original team plan.

## Scope

- FastAPI routes, shared database models, persistence and security boundaries.
- Wire Input, Slots and Output together; coordinate background imports.
- CSV HTTP upload/download, packaging, setup documentation and private phone access.

## Main files

- `Backend/main.py`
- `Backend/csv_routes.py`
- `Backend/manual_items.py`
- `Backend/conflict_routes.py`
- `Backend/database.py`
- `Backend/models.py`
- `scripts/build_team_packages.py`

`OWNED_FILES.md` in the ZIP is the exact primary-file list. Every package includes
the full runnable app so imports and shared dependencies remain available.

## Code walkthrough

1. FastAPI routes in `main.py` and the smaller routers accept validated payloads and
   obtain a short-lived SQLAlchemy session from `get_db`.
2. Manual and CSV entries pass through shared persistence and conflict checks;
   provider connectors pass through `perform_sync` and the common item-upsert path.
3. `SyncCoordinator` serializes refreshes, gives each provider its own transaction,
   records success/failure state and lets the scheduler retry temporary failures.
4. SQLite stores normalized items, work sessions, source state and bounded Outlook
   metadata. Imported records remain read-only except for explicitly local fields.
5. Offline snapshots and the service worker support read-only fallback. The package
   builder independently hashes the public source, assigns one owner per file and
   rejects private paths before producing five runnable archives.

## Demonstrate your area

1. Trace one manual event from input validation through conflict checking to database save and display.
2. Explain create-only CSV transactions and why bad whole files write nothing.
3. Explain source read-only protection, local credentials and one-worker startup.
4. Build the five packages, verify ownership and preserve all study-session history.

## Likely viva questions

**Why use FastAPI and SQLite?** FastAPI provides typed request validation and clear
routes; SQLite is sufficient for a local single-owner app and needs no separate
database server.

**How does automatic syncing work?** A single background scheduler invokes the
coordinator at the configured interval. Connected sources run sequentially in
separate transactions; failures are recorded and retried without corrupting the
next source.

**How are credentials protected?** Tokens and account sessions live in ignored local
files, are excluded from packages and logs, and source sign-ins are restricted to
the host computer rather than the phone interface.

**Why retain all study history?** Reservation totals depend on past sessions. Simple
deletion could make the planner forget completed effort and schedule it again.

**What is your integration responsibility?** Connect validated Input data and Slots
results to persistence and Output routes, preserve security/offline boundaries, and
produce the final verified package. This assigned responsibility is distinct from a
claim that one person originally wrote every integrated module.

## Verify

Run from the project root:

```powershell
python scripts/repository.py check
python scripts/test_team_handoff.py
```

Use synthetic data for shared demos. Record what you actually review, test or
change in `PROGRESS.md`; the shared application is an already-implemented baseline.
Coordinate shared API/schema and App wiring with the Integration owner.
