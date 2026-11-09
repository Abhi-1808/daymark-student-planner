# Backend dependency lock

`requirements.txt` defines the direct dependency ranges. `requirements.lock`
contains the complete resolved runtime tree, exact versions, environment markers
and SHA-256 hashes of permitted distributions. It was initially resolved against
the already-tested installed versions; adding the lock did not upgrade the running
environment. Platform-only packages such as uvloop are also pinned and hashed.

Install into a fresh virtual environment with Python 3.12 recommended:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.\.venv\Scripts\python.exe -m pip check
```

Use `.venv/bin/python` on macOS/Linux. The wheel-only option avoids an unpinned
build-time dependency tree. If no compatible wheel exists for your interpreter
or platform, choose a supported interpreter instead of disabling hash checks.
The local lock checks cover CPython 3.10 and 3.12 on Windows. A Linux Python 3.12
wheel-only resolution was checked separately; actual Linux installation and test
execution remain unverified until a hosted CI run has succeeded.

CI, the main setup guide, Android setup and generated team handoffs all install
from this file with `--require-hashes`. CI's pip cache is keyed on the lock, and
`pip check` verifies installed dependency consistency before tests run.

## Updating dependencies

Use [uv's requirements compiler](https://docs.astral.sh/uv/pip/compile/); this lock
was generated with uv 0.12.5. uv is maintainer tooling, not a runtime dependency.
To add or change a dependency, edit `requirements.txt`, then from the project root:

```powershell
uv pip compile requirements.txt --universal --python-version 3.10 --generate-hashes --output-file requirements.lock
```

The universal resolution includes platform/Python markers instead of freezing
every package in a developer's unrelated environment. Existing locked versions
are preferred. To deliberately update one package and any required dependencies:

```powershell
uv pip compile requirements.txt --universal --python-version 3.10 --generate-hashes --upgrade-package fastapi --output-file requirements.lock
```

Use `--upgrade` for an intentional full refresh. Review the version/hash diff,
install into a new environment using the hash-checked command above, and run both
backend suites before committing `requirements.txt` and `requirements.lock`
together. Never copy a pip freeze from a general-purpose Python environment.

The artifact hashes and exact pins make installations repeatable for each target
environment; they do not prove packages are bug-free or replace dependency
maintenance. Environment markers intentionally select different platform-specific
packages on Windows and Linux.
