import hashlib
import json
import sqlite3
import time
from contextlib import contextmanager
from uuid import uuid4

from .models import Preferences, Record

RECORD_DEFAULTS = Record(kind="task", title="Item").model_dump()

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
  id TEXT PRIMARY KEY, source TEXT NOT NULL, external_id TEXT,
  payload TEXT NOT NULL, modified INTEGER NOT NULL,
  UNIQUE(source, external_id)
);
CREATE TABLE IF NOT EXISTS preferences (id INTEGER PRIMARY KEY CHECK (id = 1), payload TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS dismissed (
  id TEXT PRIMARY KEY, mate TEXT NOT NULL, expected TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS connections (
  provider TEXT PRIMARY KEY, token TEXT NOT NULL, synced TEXT, error TEXT
);
CREATE TABLE IF NOT EXISTS sessions (digest TEXT PRIMARY KEY, expires INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS oauth_states (
  state TEXT PRIMARY KEY, provider TEXT NOT NULL, session TEXT NOT NULL,
  verifier TEXT NOT NULL, expires INTEGER NOT NULL
);
"""


class Store:
    def __init__(self, path):
        self.path = path

    @contextmanager
    def tx(self):
        conn = sqlite3.connect(self.path, timeout=15)
        try:
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init(self):
        self.path.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            self.path.chmod(0o600)
            conn.execute("PRAGMA journal_mode = WAL")
            conn.executescript(SCHEMA)
        finally:
            conn.close()

    def snapshot(self):
        with self.tx() as conn:
            conn.execute("BEGIN")
            return self.read_snapshot(conn)

    def read_snapshot(self, conn):
        preferences = conn.execute("SELECT payload FROM preferences WHERE id = 1").fetchone()
        records = conn.execute("SELECT * FROM records ORDER BY modified, id").fetchall()
        dismissed = conn.execute("SELECT * FROM dismissed").fetchall()
        revision = digest(json.dumps([
            preferences["payload"] if preferences else "",
            [(row["id"], row["modified"]) for row in records],
            [tuple(row) for row in dismissed],
        ]))
        return {
            "preferences": json.loads(preferences["payload"]) if preferences else Preferences().model_dump(),
            "records": [self.unpack(row) for row in records],
            "dismissed": [dict(row) for row in dismissed],
            "revision": revision,
        }

    def add_plan(self, revision, blocks):
        with self.tx() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if self.read_snapshot(conn)["revision"] != revision:
                return False
            for block in blocks:
                conn.execute("INSERT INTO records VALUES (?, 'manual', NULL, ?, ?)",
                             (uuid4().hex, block.model_dump_json(), time.time_ns()))
        return True

    def dismiss(self, revision, record_id, mate, expected):
        with self.tx() as conn:
            conn.execute("BEGIN IMMEDIATE")
            snapshot = self.read_snapshot(conn)
            ids = {record["id"]: record["source"] for record in snapshot["records"]}
            if (snapshot["revision"] != revision or ids.get(record_id) != "google-calendar"
                    or ids.get(mate) not in ("camu", "camu-feed")):
                return False
            conn.execute("INSERT OR REPLACE INTO dismissed VALUES (?, ?, ?)", (record_id, mate, expected))
        return True

    def restore(self, record_id):
        with self.tx() as conn:
            conn.execute("DELETE FROM dismissed WHERE id=?", (record_id,))

    @staticmethod
    def unpack(row):
        return {**RECORD_DEFAULTS, "id": row["id"], "source": row["source"], **json.loads(row["payload"])}

    def save(self, record: Record, record_id=None):
        with self.tx() as conn:
            if record_id is None:
                record_id = uuid4().hex
                conn.execute("INSERT INTO records VALUES (?, 'manual', NULL, ?, ?)",
                             (record_id, record.model_dump_json(), time.time_ns()))
            else:
                result = conn.execute("UPDATE records SET payload=?, modified=? WHERE id=? AND source='manual'",
                                      (record.model_dump_json(), time.time_ns(), record_id))
                if result.rowcount != 1:
                    return None
        return {"id": record_id, "source": "manual", **record.model_dump()}

    def delete(self, record_id):
        with self.tx() as conn:
            return conn.execute("DELETE FROM records WHERE id=? AND source='manual'", (record_id,)).rowcount == 1

    def read_preferences(self):
        with self.tx() as conn:
            saved = conn.execute("SELECT payload FROM preferences WHERE id=1").fetchone()
        return json.loads(saved["payload"]) if saved else Preferences().model_dump()

    def preferences(self, preferences):
        with self.tx() as conn:
            conn.execute("INSERT OR REPLACE INTO preferences VALUES (1, ?)", (preferences.model_dump_json(),))
        return preferences

    @staticmethod
    def upsert(conn, source, entries):
        for external_id, record in entries.items():
            conn.execute("""
              INSERT INTO records VALUES (?, ?, ?, ?, ?)
              ON CONFLICT(source, external_id) DO UPDATE SET payload=excluded.payload, modified=excluded.modified
              WHERE records.payload != excluded.payload
            """, (uuid4().hex, source, external_id, record.model_dump_json(), time.time_ns()))

    def clear_import(self, source):
        with self.tx() as conn:
            conn.execute("DELETE FROM records WHERE source=?", (source,))

    def import_records(self, source, entries):
        with self.tx() as conn:
            self.upsert(conn, source, entries)

    def connection(self, provider):
        with self.tx() as conn:
            row = conn.execute("SELECT * FROM connections WHERE provider=?", (provider,)).fetchone()
            return dict(row) if row else None

    def connection_status(self):
        with self.tx() as conn:
            rows = conn.execute("SELECT provider, synced, error FROM connections").fetchall()
            return {row["provider"]: dict(row) for row in rows}

    def connect(self, provider, token):
        with self.tx() as conn:
            conn.execute("INSERT OR REPLACE INTO connections VALUES (?, ?, NULL, NULL)", (provider, token))
            for source in provider_sources(provider):
                conn.execute("DELETE FROM records WHERE source=?", (source,))

    def disconnect(self, provider):
        with self.tx() as conn:
            conn.execute("DELETE FROM connections WHERE provider=?", (provider,))
            for source in provider_sources(provider):
                conn.execute("DELETE FROM records WHERE source=?", (source,))

    def finish_sync(self, provider, old_token, token, feeds, synced, error=None):
        with self.tx() as conn:
            result = conn.execute("""
              UPDATE connections SET token=?, synced=COALESCE(?, synced), error=?
              WHERE provider=? AND token=?
            """, (token, synced, error, provider, old_token))
            if not result.rowcount:
                return
            for source, entries in feeds.items():
                existing = conn.execute("SELECT external_id FROM records WHERE source=?", (source,)).fetchall()
                removed = [(source, row["external_id"]) for row in existing if row["external_id"] not in entries]
                conn.executemany("DELETE FROM records WHERE source=? AND external_id=?", removed)
                self.upsert(conn, source, entries)

    def issue_session(self, token):
        with self.tx() as conn:
            conn.execute("DELETE FROM sessions WHERE expires <= ?", (int(time.time()),))
            conn.execute("INSERT INTO sessions VALUES (?, ?)", (digest(token), int(time.time()) + 604800))

    def valid_session(self, token):
        with self.tx() as conn:
            return bool(conn.execute("SELECT 1 FROM sessions WHERE digest=? AND expires>?",
                                     (digest(token), int(time.time()))).fetchone())

    def revoke_session(self, token):
        with self.tx() as conn:
            session = digest(token)
            conn.execute("DELETE FROM sessions WHERE digest=?", (session,))
            conn.execute("DELETE FROM oauth_states WHERE session=?", (session,))

    def oauth_state(self, state, provider, session, verifier):
        with self.tx() as conn:
            conn.execute("DELETE FROM oauth_states WHERE expires<=?", (int(time.time()),))
            conn.execute("INSERT INTO oauth_states VALUES (?, ?, ?, ?, ?)",
                         (digest(state), provider, digest(session), verifier, int(time.time()) + 600))

    def consume_state(self, state, provider, session):
        with self.tx() as conn:
            return conn.execute("""
              DELETE FROM oauth_states WHERE state=? AND provider=? AND session=? AND expires>?
              RETURNING verifier
            """, (digest(state), provider, digest(session), int(time.time()))).fetchone()


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def provider_sources(provider):
    return {"google": ("google-calendar", "google-tasks"), "microsoft": ("outlook",), "bennett": ("bennett-feed",), "camu": ("camu-feed",)}[provider]
