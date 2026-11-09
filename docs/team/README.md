# Five-person handoff matching the original plan

| Person | Original role | Final area | Guide |
| --- | --- | --- | --- |
| Suraj | Input | Manual validation, CSV files and authorized provider inputs | [Input](01-input.md) |
| Rishabh | Slots sorting | Sorting, conflicts, free slots and Python task allocation | [Slots](02-slots.md) |
| Ayush | Output | Calendar/Today views, warnings, previews and interface feedback | [Output](03-output.md) |
| Atulaya | Testing | Unit, integration, browser, offline and packaging verification | [Testing](04-testing.md) |
| You | Integration | API wiring, persistence, source coordination, setup and delivery | [Integration](05-integration.md) |

This replaces the earlier technical-module split for new handoffs. It preserves
original role names while covering the larger final application. Roles are
responsibilities, not an assertion of equal line counts or past hours worked.

Every ZIP contains the complete runnable public app, MODULE.md, OWNED_FILES.md,
START_HERE.md and an unchecked PROGRESS.md for its assigned member. Each public
file has exactly one primary owner in modules.json. Shared changes are reviewed
with the Integration owner, and tests are coordinated with Atulaya.

Rishabh explains the pure conflict algorithm; Integration explains the routes and
save boundary; Suraj explains input validation and CSV; Ayush demonstrates the
warnings; Atulaya provides the test evidence. Saving blocks timed overlaps until
an explicit override. Study also advises about short room changes. The conflict
scan has O(n²) worst-case work, including its potentially quadratic output.

## Suggested presentation order

1. **Integration:** introduce the problem, architecture and end-to-end data flow.
2. **Input:** demonstrate manual entry, CSV validation and connected sources.
3. **Slots:** explain conflict detection, free windows and study allocation.
4. **Output:** demonstrate Today, calendar views, previews and visual feedback.
5. **Testing:** show the automated evidence, limitations and final verification.

Each person should explain their module summary, trace one real code path, run one
short demonstration and answer the questions in their module guide. The whole
group should still understand the complete project and its main limitations.

## Responsibility record

These are assigned responsibilities for reviewing, presenting and maintaining the
completed shared project. They are not a statement that each person originally
implemented every file in their area or contributed equal historical hours.
`PROGRESS.md` should record only work the named member actually reviews, tests or
changes after receiving the shared baseline.

Packages contain no Git history, account connections, credentials, inbox data,
private calendars, databases, installed dependencies or compiled output. Use the
synthetic demo in START_HERE.md or configure your own account. Preserve study
history and keep duplicate removal an explicit reviewed action.

The builder records HEAD and per-file hashes. Public uncommitted changes are
allowed and are labelled working-tree snapshots; commit first when archives must
match a committed revision. Older archives are not overwritten automatically.

From the project root:

```powershell
python scripts/build_team_packages.py
python scripts/test_team_handoff.py
```

The default output is deliverables/team/. Extract one ZIP per person, read its
module guide and record actual checks and follow-up changes in PROGRESS.md.
Hosted GitHub CI and the real Android trial remain unverified.
