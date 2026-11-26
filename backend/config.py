import os
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


class Settings:
    def __init__(self):
        self.origin = os.getenv("DAYMARK_ORIGIN", "http://localhost:8000").rstrip("/")
        url = urlsplit(self.origin)
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.path or url.query or url.fragment:
            raise RuntimeError("DAYMARK_ORIGIN must be an HTTP(S) origin without a path")
        self.secure = url.scheme == "https"
        self.password = os.getenv("DAYMARK_PASSWORD", "")
        if self.password and len(self.password) < 12:
            raise RuntimeError("DAYMARK_PASSWORD must be at least 12 characters")
        if not self.secure and url.hostname not in ("localhost", "127.0.0.1", "::1"):
            raise RuntimeError("Remote Daymark access requires HTTPS")
        if self.secure and not self.password:
            raise RuntimeError("Remote Daymark access requires DAYMARK_PASSWORD")
        self.db = Path(os.getenv("DAYMARK_DB", ROOT / "data" / "daymark.sqlite3")).expanduser()
        self.key = os.getenv("DAYMARK_TOKEN_KEY", "")
        self.google_id = os.getenv("DAYMARK_GOOGLE_CLIENT_ID", "")
        self.google_secret = os.getenv("DAYMARK_GOOGLE_CLIENT_SECRET", "")
        self.microsoft_id = os.getenv("DAYMARK_MICROSOFT_CLIENT_ID", "")
        self.microsoft_secret = os.getenv("DAYMARK_MICROSOFT_CLIENT_SECRET", "")
        self.microsoft_tenant = os.getenv("DAYMARK_MICROSOFT_TENANT", "common")
        self.sync_seconds = int(os.getenv("DAYMARK_SYNC_SECONDS", "300"))
        if self.sync_seconds < 0 or 0 < self.sync_seconds < 60:
            raise RuntimeError("DAYMARK_SYNC_SECONDS must be 0 or at least 60")
