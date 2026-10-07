"""SQLite persistence: workflow types, runs, events. JSON blobs keep the schema tiny."""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

_DDL = """
CREATE TABLE IF NOT EXISTS types (
  name TEXT NOT NULL, version INTEGER NOT NULL, yaml TEXT NOT NULL,
  created_at TEXT NOT NULL, PRIMARY KEY (name, version));
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, type TEXT NOT NULL, version INTEGER NOT NULL,
  status TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS runs_status ON runs(status, type);
CREATE TABLE IF NOT EXISTS events (
  seq INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, ts TEXT NOT NULL,
  kind TEXT NOT NULL, step_id TEXT, data TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS events_run ON events(run_id, seq);
"""


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: str | Path = ":memory:"):
        self._lock = threading.RLock()
        self._db = sqlite3.connect(str(path), check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        with self._lock:
            self._db.executescript(_DDL)

    # types -------------------------------------------------------------
    def put_type(self, name: str, version: int, yaml_text: str) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO types(name, version, yaml, created_at) VALUES (?,?,?,?)",
                (name, version, yaml_text, now_iso()),
            )
            self._db.commit()

    def get_type_yaml(self, name: str, version: int | None = None) -> tuple[int, str] | None:
        with self._lock:
            if version is None:
                row = self._db.execute(
                    "SELECT version, yaml FROM types WHERE name=? ORDER BY version DESC LIMIT 1", (name,)
                ).fetchone()
            else:
                row = self._db.execute("SELECT version, yaml FROM types WHERE name=? AND version=?", (name, version)).fetchone()
        return (row["version"], row["yaml"]) if row else None

    def list_types(self) -> list[dict]:
        with self._lock:
            rows = self._db.execute(
                "SELECT name, MAX(version) AS version, MAX(created_at) AS created_at FROM types GROUP BY name ORDER BY name"
            ).fetchall()
        return [dict(r) for r in rows]

    # runs --------------------------------------------------------------
    def put_run(self, run: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT OR REPLACE INTO runs(id, type, version, status, data, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                (run["id"], run["type"], run["version"], run["status"], json.dumps(run), run["created_at"], now_iso()),
            )
            self._db.commit()

    def get_run(self, run_id: str) -> dict | None:
        with self._lock:
            row = self._db.execute("SELECT data FROM runs WHERE id=?", (run_id,)).fetchone()
        return json.loads(row["data"]) if row else None

    def list_runs(self, status: str | None = None, type_name: str | None = None, limit: int = 50) -> list[dict]:
        q, args = "SELECT data FROM runs", []
        conds = []
        if status:
            conds.append("status=?"); args.append(status)
        if type_name:
            conds.append("type=?"); args.append(type_name)
        if conds:
            q += " WHERE " + " AND ".join(conds)
        q += " ORDER BY created_at DESC LIMIT ?"
        args.append(limit)
        with self._lock:
            rows = self._db.execute(q, args).fetchall()
        return [json.loads(r["data"]) for r in rows]

    # events ------------------------------------------------------------
    def add_event(self, run_id: str, kind: str, step_id: str | None = None, **data) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO events(run_id, ts, kind, step_id, data) VALUES (?,?,?,?,?)",
                (run_id, now_iso(), kind, step_id, json.dumps(data)),
            )
            self._db.commit()

    def events(self, run_id: str) -> list[dict]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM events WHERE run_id=? ORDER BY seq", (run_id,)).fetchall()
        return [{"seq": r["seq"], "ts": r["ts"], "kind": r["kind"], "step_id": r["step_id"], **json.loads(r["data"])} for r in rows]
