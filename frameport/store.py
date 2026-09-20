from __future__ import annotations
import json
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

from .platform_store import PlatformStore

class Store(PlatformStore):
    """Every update is one SQLite transaction; no in-memory source of truth."""
    def __init__(self, root: Path):
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / "jobs.sqlite3"
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, created REAL, updated REAL, status TEXT, record TEXT)")

        self.migrate_platform()

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        return db

    def create(self, request: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        record = dict(id=uuid.uuid4().hex, created=now, updated=now, status="queued", stage="Queued", progress=0, request=request, events=[], error=None, report=None, revision=0, cancelled=False)
        self._write(record)
        return record

    def _write(self, r: dict[str, Any]):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO jobs VALUES (?,?,?,?,?)", (r["id"], r["created"], r["updated"], r["status"], json.dumps(r)))

    def get(self, ident: str):
        with self.connect() as db:
            row = db.execute("SELECT record FROM jobs WHERE id=?", (ident,)).fetchone()
        return json.loads(row[0]) if row else None

    def update(self, ident: str, **values):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM jobs WHERE id=?", (ident,)).fetchone()
            if not row:
                return None
            r = json.loads(row[0])
            r.update(values)
            r["updated"] = time.time()
            db.execute("UPDATE jobs SET updated=?,status=?,record=? WHERE id=?", (r["updated"], r["status"], json.dumps(r), ident))
            return r

    def event(self, ident: str, stage: str, progress: int, message: str):
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT record FROM jobs WHERE id=?", (ident,)).fetchone()
            if not row:
                return
            r = json.loads(row[0])
            r.update(stage=stage, progress=progress, updated=time.time())
            r["events"] = (r["events"] + [dict(time=time.time(), stage=stage, message=message)])[-100:]
            db.execute("UPDATE jobs SET updated=?,record=? WHERE id=?", (r["updated"], json.dumps(r), ident))

    def list(self, limit=100):
        with self.connect() as db:
            rows = db.execute("SELECT record FROM jobs ORDER BY created DESC LIMIT ?", (limit,)).fetchall()
        return [json.loads(r[0]) for r in rows]

    def delete(self, ident):
        with self.connect() as db:
            db.execute("DELETE FROM jobs WHERE id=?", (ident,))
            db.execute("DELETE FROM requests WHERE job_id=?", (ident,))
            db.execute("DELETE FROM revisions WHERE job_id=?", (ident,))
