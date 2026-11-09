"""Build five runnable team handoffs from public source, without local account data."""

from datetime import datetime, timedelta, timezone
from fnmatch import fnmatch
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

from repository import ROOT, private_path, public_files

SECRET_PATTERNS = (
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----",
    rb"GOCSPX-[A-Za-z0-9_-]{12,}", rb"ya29\.[A-Za-z0-9_-]{30,}",
    rb"AIza[0-9A-Za-z_-]{30,}", rb"gh[pousr]_[A-Za-z0-9]{30,}",
    rb"github_pat_[A-Za-z0-9_]{40,}",
)


def source_snapshot(root=ROOT):
    if root != ROOT:
        raise ValueError("Build from this checkout's public source.")
    result = {}
    for name in public_files():
        if private_path(name):
            raise ValueError(f"Private/generated file cannot be packaged: {name}")
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            raise ValueError(f"Source path leaves the checkout: {name}")
        content = path.read_bytes()
        if any(re.search(pattern, content) for pattern in SECRET_PATTERNS):
            raise ValueError(f"Possible credential format in {name}; review before packaging.")
        result[name] = content
    return result


def assign_ownership(names, modules):
    if len(modules) != 5 or {module["id"] for module in modules} != {"01", "02", "03", "04", "05"}:
        raise ValueError("Define exactly five unique team modules.")
    if any(not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", module["slug"]) for module in modules):
        raise ValueError("Module slugs must contain lowercase words separated by hyphens.")
    ownership = {module["id"]: [] for module in modules}
    for name in names:
        matches = [module for module in modules if any(fnmatch(name, pattern) for pattern in module["patterns"])]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one primary owner for {name}; found {len(matches)}.")
        ownership[matches[0]["id"]].append(name)
    if any(not paths for paths in ownership.values()):
        raise ValueError("Each module needs primary files.")
    return ownership


def start_here(module, commit):
    return f'''# Daymark - Part {module["id"]}: {module["title"]}

Assigned role: **{module.get("assignee", "Team member")}**.

This is your team module, based on Daymark commit `{commit}`. The `daymark/`
folder contains the full runnable shared application so your module has its
dependencies. Your separate primary files are listed in `OWNED_FILES.md`;
your feature responsibilities are explained in `MODULE.md`.

## Start a synthetic demo on Windows

Use Python 3.10+ and Node 22+. Extract the ZIP before running commands.
Open a terminal in the extracted package:

```powershell
Set-Location daymark
python -m venv .venv
.\\.venv\\Scripts\\python.exe -m pip install --require-hashes --only-binary=:all: -r requirements.lock
.\\.venv\\Scripts\\python.exe scripts/seed_demo.py
$env:DATABASE_URL = "sqlite:///./daymark-demo.db"
$env:AUTO_SYNC_ENABLED = "false"
.\\.venv\\Scripts\\python.exe -m uvicorn Backend.main:app --host 127.0.0.1 --port 8000
```

In another terminal, open this package's `daymark/Frontend` folder:

```powershell
npm.cmd ci
npm.cmd run dev
```

Open http://localhost:5173. Use the frontend port printed by Vite if 5173 is busy.
Only run one package's backend at a time on port 8000. On macOS/Linux, replace
the Python executable with `.venv/bin/python` and use `export DATABASE_URL=...`
and `export AUTO_SYNC_ENABLED=false` instead of the PowerShell environment lines.

The optional demo uses generated classes, matching imported copies, assignments,
subjects, attendance counts and an exam. It does not connect to any real account.
`seed_demo.py` never replaces an existing demo database. To reset a demo, extract
a fresh copy to a different folder and seed that copy.

For live integrations, follow `daymark/docs/integrations.md` with your own accounts.
No credentials or student data are included. Demo source labels are examples,
not proof of an active Google, LMS or MyCamu connection.

## Your part

Read `MODULE.md`, follow its demo sequence, and record your actual checks and
changes in `PROGRESS.md`. The app features already exist in the shared baseline;
the progress template starts unchecked for your own review and follow-up work.

The ownership list identifies primary files. Coordinate shared API/schema and
application wiring with the Integration owner, and verification with Atulaya.

## Optional local Git history

The ZIP has no `.git` folder. If you want local version history or want to run
the repository/package-builder commands, initialize Git inside `daymark/`:

```powershell
git init
git add .
git commit -m "Start from shared Daymark baseline"
```

Use your own Git name/email when committing. This creates local history only;
it does not add a remote or push anything to GitHub.
'''


def progress_template(module, commit):
    return f'''# Progress - Part {module["id"]}: {module["title"]}

Assigned member: {module.get("assignee", "Team member")}
Member name:
Review date:
Shared baseline: `{commit}` (already implemented)

## My review and verification

- [ ] Installed dependencies and opened the local app.
- [ ] Read the module's main files and explained its data flow.
- [ ] Ran the module's relevant tests and recorded the result below.
- [ ] Completed the module's demo sequence with synthetic data.
- [ ] Reviewed shared-file dependencies with their owners.

## My changes after receiving the baseline

| Date | Change or investigation | Files | Verification | Status |
| --- | --- | --- | --- | --- |
| | | | | |

## Demo evidence

- Screenshots or recording:
- Test commands and actual results:
- What works:
- Limitations or blockers:

## Next step

Describe your next agreed task and the checks you will use to verify it.
'''


def verify_archive(path, manifest):
    with zipfile.ZipFile(path) as archive:
        if archive.testzip() is not None:
            raise ValueError(f"ZIP integrity check failed: {path.name}")
        expected = {"START_HERE.md", "MODULE.md", "PROGRESS.md", "OWNED_FILES.md", "manifest.json"} | {
            "daymark/" + name for name in manifest["source_sha256"]
        }
        if set(archive.namelist()) != expected:
            raise ValueError(f"Unexpected archive contents: {path.name}")
        for name in archive.namelist():
            relative = PurePosixPath(name)
            if relative.is_absolute() or ".." in relative.parts or ".git" in relative.parts or private_path(name):
                raise ValueError(f"Unsafe/private archive path: {name}")
        for name, expected_hash in manifest["source_sha256"].items():
            if hashlib.sha256(archive.read("daymark/" + name)).hexdigest() != expected_hash:
                raise ValueError(f"Source hash mismatch: {name}")


def build_packages(output=None):
    source = source_snapshot()
    modules = json.loads(source["docs/team/modules.json"])
    ownership = assign_ownership(source, modules)
    commit = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    created = datetime.now(timezone(timedelta(hours=5, minutes=30))).date().isoformat()
    hashes = {name: hashlib.sha256(content).hexdigest() for name, content in source.items()}
    output = Path(output).resolve() if output else ROOT / "deliverables/team"
    output.mkdir(parents=True, exist_ok=True)
    packages = []
    for module in modules:
        manifest = {"module_id": module["id"], "module": module["title"], "assignee": module.get("assignee"), "created_on": created,
                    "base_commit": commit, "source_type": "public-working-tree-snapshot",
                    "primary_files": ownership[module["id"]], "source_sha256": hashes,
                    "shared_baseline": "Full app included; module guide identifies team responsibility."}
        target = output / f'daymark-part-{module["id"]}-{module["slug"]}.zip'
        if target.resolve().parent != output:
            raise ValueError("An archive target leaves the chosen output directory.")
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("START_HERE.md", start_here(module, commit))
            archive.writestr("MODULE.md", source["docs/team/" + module["guide"]])
            archive.writestr("PROGRESS.md", progress_template(module, commit))
            archive.writestr("OWNED_FILES.md", f'# Part {module["id"]}: {module["title"]}\n\n'
                             'These are your primary files inside the shared `daymark/` folder.\n'
                             'The remaining files provide the dependencies needed to run the app.\n\n'
                             + ''.join(f'- `{name}`\n' for name in sorted(ownership[module["id"]])))
            archive.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
            for name, content in source.items():
                archive.writestr("daymark/" + name, content)
        verify_archive(target, manifest)
        packages.append(target)
    return packages


if __name__ == "__main__":
    for package in build_packages():
        print(f"{package.name}: {package.stat().st_size / 1024:.0f} KB; verified")
