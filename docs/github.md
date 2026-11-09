# GitHub preparation

The project is prepared locally. No GitHub remote, push or publication is required
to run it, and no repository is selected by this setup.

## What is included

- A README and separate feature, API, integration and structure documentation.
- Python/JavaScript formatting defaults and consistent Git line endings.
- Backend and frontend environment examples containing no account credentials.
- A GitHub Actions workflow for tests, production build and mocked browser flows.
- A pull request template for describing changes and verification.
- Ignore rules and a filename check for local credentials, sessions, calendars,
  database files, dependency folders and generated output.

Run these local checks before preparing a commit:

```powershell
python scripts/repository.py check --history
git diff --check
git status --short
```

The repository check inspects filenames, not file contents. Review diffs for any
personal data before sharing code. Account sessions and downloaded calendars stay
local; unit and browser tests use fixture data and need no student credentials.

## Later: connect a repository

When you decide to publish, choose the GitHub account and an empty repository.
The Git author and the GitHub account are separate settings; verify both first.

```powershell
git config --get user.name
git config --get user.email
git branch --show-current
git remote -v
```

Then review the files, create a local commit and add the chosen remote. Replace
`YOUR_ACCOUNT/daymark` with the repository you own:

```powershell
git add .
git diff --cached --stat
git diff --cached
git commit -m "Add Daymark integrations, study tools and project structure"
git remote add origin https://github.com/YOUR_ACCOUNT/daymark.git
git push -u origin HEAD
```

These commands are instructions for a future publishing step; they are not run
by this setup. They preserve the existing commit history and current branch name.
GitHub authentication is handled by Git's credential manager or your chosen GitHub
client. Personal access tokens never belong in source files or remote URLs.

## Continuous integration

After the repository is pushed, `.github/workflows/ci.yml` runs on pushes and pull
requests, with an additional manual trigger. It uses Python 3.12, Node 24 and the
Ubuntu 24.04 hosted runner's Chrome. Jobs have read-only repository permissions and do not
deploy the website. Browser tests create their own temporary local server and
profile, and use mocked API responses.

The checks run in two jobs:

| Job | Order of checks |
| --- | --- |
| Backend | Public-file check, dependency installation, backend core tests, additional team-packaging and isolated-demo tests. |
| Frontend | Dependency installation, frontend core tests, production build, browser checks against `Frontend/dist`. |

The public-file check uses only Python's standard library, so it runs before pip
installs the backend requirements. Browser QA reads the compiled `dist` directory;
the production build must finish successfully before those browser checks run.

Test totals have separate scopes: add the backend and frontend unit-test counts
for the **core total**, then include the team-handoff suite for the **total with
packaging tests**. Production builds and browser scenarios are additional checks,
not extra unit tests. Each suite prints its current count in its own named CI step.

Action references are pinned to verified release commits: [checkout v7.0.1](https://github.com/actions/checkout/releases/tag/v7.0.1),
[setup-python v7.1.0](https://github.com/actions/setup-python/releases/tag/v7.1.0),
and [setup-node v7.1.0](https://github.com/actions/setup-node/releases/tag/v7.1.0).
These actions run on Node 24 internally; that is separate from the Python/Node
versions they install for the project. A self-hosted runner would need [Actions
Runner 2.327.1 or later](https://github.com/actions/runner/releases/tag/v2.327.1)
for that action runtime. The configured jobs use GitHub-hosted Ubuntu runners.

Local checks do not establish that GitHub-hosted CI has passed. That result is
available only after an authorized push or workflow dispatch; no such run is
started by the local setup.
