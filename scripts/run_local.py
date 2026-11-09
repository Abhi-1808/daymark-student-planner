"""Start Daymark's compiled app and API on one loopback address."""

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def phone_identity(status):
    if status.get("BackendState") != "Running":
        raise ValueError("Sign in to Tailscale on the computer and connect it first.")
    device = status.get("Self") or {}
    user = (status.get("User") or {}).get(str(device.get("UserID")), {})
    login = user.get("LoginName", "")
    name = device.get("DNSName", "").rstrip(".")
    from Backend.private_access import private_settings
    return private_settings(f"https://{name}", login)


def tailscale_executable():
    # Phone identity trusts the locally installed CLI and OS, like Daymark itself.
    # On Windows, never let a working-directory/PATH shim supply that identity.
    if sys.platform == "win32":
        folder = Path(os.environ.get("ProgramW6432") or os.environ.get("ProgramFiles") or "C:/Program Files")
        if not folder.is_absolute():
            return None
        candidate = folder / "Tailscale" / "tailscale.exe"
        return str(candidate.resolve()) if candidate.is_file() else None
    executable = shutil.which("tailscale")
    return str(Path(executable).resolve()) if executable else None


def prepare_phone(parser, port):
    executable = tailscale_executable()
    if not executable:
        parser.error("Install Tailscale on your computer and phone, and sign in to the same account. See docs/android.md.")
    logging.getLogger("daymark.launcher").info("Tailscale CLI resolved", extra={
        "event": "daymark.phone.cli_resolved", "executable": executable,
    })
    try:
        result = subprocess.run([executable, "status", "--json"], capture_output=True, text=True,
                                check=True, timeout=10)
        origin, user = phone_identity(json.loads(result.stdout))
    except (OSError, subprocess.SubprocessError, ValueError, TypeError, AttributeError):
        parser.error("Tailscale is not connected with a personal user and HTTPS DNS name. Connect it first; see docs/android.md.")
    os.environ["DAYMARK_PRIVATE_ORIGIN"] = origin
    os.environ["DAYMARK_PRIVATE_USER"] = user
    print(f"Phone address: {origin}", flush=True)
    print(f"After this server starts, run in a second terminal:\n  tailscale serve --bg http://127.0.0.1:{port}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--phone", action="store_true", help="Restrict private HTTPS access to this computer's Tailscale login")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Choose a port between 1 and 65535.")
    if not (ROOT / "Frontend" / "dist" / "index.html").is_file():
        parser.error("Build the frontend first: cd Frontend; npm ci; npm run build")
    from Backend.private_access import private_settings
    from Backend.runtime import configure_logging
    import uvicorn

    configure_logging()
    if args.phone:
        prepare_phone(parser, args.port)
    try:
        private_settings(os.getenv("DAYMARK_PRIVATE_ORIGIN", ""), os.getenv("DAYMARK_PRIVATE_USER", ""))
    except ValueError as error:
        parser.error(str(error))
    os.chdir(ROOT)
    os.environ.setdefault("FRONTEND_URL", f"http://127.0.0.1:{args.port}")
    # The application also holds a DB-specific OS lock. Identity checks require
    # the real socket peer: never trust forwarded IP headers in this launcher.
    uvicorn.run("Backend.main:app", host="127.0.0.1", port=args.port, workers=1,
                proxy_headers=False, access_log=False, log_config=None)


if __name__ == "__main__":
    main()
