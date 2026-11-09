"""Inspect the public project tree without reading credentials or local calendars."""

import argparse
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PRIVATE_NAMES = (
    "credentials.json", "google-token.json*", "camu-session.json*", "outlook-connection.json*",
    "lms-connection.json*", "*.db", "*.db-*", "*.sqlite", "*.sqlite3", "*.ics",
    "*.pem", "*.key", "*.p12", "*.pfx", "*.log", "daymark-manual-items*.csv",
)
GENERATED_DIRECTORIES = {"node_modules", "dist", "__pycache__", ".venv", "venv", "coverage"}


def git(*arguments):
    return subprocess.check_output(["git", *arguments], cwd=ROOT)


def public_files():
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").decode("utf-8").split("\0")
    return sorted({name for name in names if name and (ROOT / name).is_file()})


def private_path(name):
    path = PurePosixPath(name)
    return (any(part in GENERATED_DIRECTORIES for part in path.parts)
            or any(fnmatch(path.name.lower(), pattern) for pattern in PRIVATE_NAMES)
            or (path.name.startswith(".env") and path.name != ".env.example"))


def print_tree(names):
    tree = {}
    for name in names:
        branch = tree
        for part in PurePosixPath(name).parts:
            branch = branch.setdefault(part, {})

    def render(branch, prefix=""):
        entries = sorted(branch, key=lambda name: (not bool(branch[name]), name.lower()))
        for index, name in enumerate(entries):
            last = index == len(entries) - 1
            print(prefix + ("`-- " if last else "|-- ") + name + ("/" if branch[name] else ""))
            render(branch[name], prefix + ("    " if last else "|   "))
    print("Daymark/")
    render(tree)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("tree", "check"))
    parser.add_argument("--history", action="store_true", help="Also check committed filenames across local refs.")
    arguments = parser.parse_args()
    names = public_files()
    failures = {name for name in names if private_path(name)}
    if arguments.history:
        history = git("rev-list", "--objects", "--all").decode("utf-8").splitlines()
        failures.update(line.split(" ", 1)[1] for line in history if " " in line and private_path(line.split(" ", 1)[1]))
    if failures:
        print("Private or generated paths must be excluded before sharing:")
        for name in sorted(failures):
            print("  " + name)
        return 1
    if arguments.command == "tree":
        print_tree(names)
    else:
        print(f"Checked {len(names)} public files: no local credential, calendar, database or generated paths included.")
        if arguments.history:
            print("Committed filenames across local refs also passed. File contents were not inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
