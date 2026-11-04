"""
SQLite storage for everything that has to outlive a page reload: open cases,
approval decisions, the gate's log and the operational audit trail.

The database file is backend/knowledge/resolvia.db unless RESOLVIA_DB points
somewhere else. Evaluation scripts and tests set RESOLVIA_DB=":memory:" so a
batch run never touches the real trail.

The audit tables are append-only from the app's point of view: nothing in
the backend updates or deletes a row except reset(), which only the tests and
offline scripts call.
"""

import json
import os
import sqlite3
import shutil
import threading
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_PATH = os.path.join(HERE, "knowledge", "resolvia.db")
# a ready-made working day (build_demo_day.py), copied in when the app starts fresh
DEMO_DAY_PATH = os.path.join(HERE, "knowledge", "demo_day.db")

_LOCK = threading.RLock()
_CONN = None
_PATH = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    break_id   TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    data       TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    break_id  TEXT PRIMARY KEY,
    decision  TEXT NOT NULL,
    approver  TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    notes     TEXT
);
CREATE TABLE IF NOT EXISTS gate_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    break_id  TEXT,
    event     TEXT NOT NULL,
    detail    TEXT,
    timestamp TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT UNIQUE NOT NULL,
    timestamp  TEXT NOT NULL,
    actor_id   TEXT NOT NULL,
    action     TEXT NOT NULL,
    break_id   TEXT,
    detail     TEXT,
    source     TEXT,
    metadata   TEXT,
    dedupe_key TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS events_break ON events (break_id);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _conn():
    global _CONN, _PATH
    path = os.environ.get("RESOLVIA_DB") or DEFAULT_PATH
    with _LOCK:
        if _CONN is None or path != _PATH:
            if _CONN is not None:
                _CONN.close()
            if path != ":memory:":
                os.makedirs(os.path.dirname(path), exist_ok=True)
                if path == DEFAULT_PATH and not os.path.exists(path) and os.path.exists(DEMO_DAY_PATH):
                    shutil.copyfile(DEMO_DAY_PATH, path)
            _CONN = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
            _CONN.row_factory = sqlite3.Row
            _CONN.executescript(SCHEMA)
            _PATH = path
        return _CONN


def _run(sql, args=()):
    with _LOCK:
        return _conn().execute(sql, args)


# cases

def save_case(case):
    _run("INSERT INTO cases (break_id, status, data, updated_at) VALUES (?, ?, ?, ?) "
         "ON CONFLICT(break_id) DO UPDATE SET status=excluded.status, data=excluded.data, "
         "updated_at=excluded.updated_at",
         (case["break_id"], case["status"], json.dumps(case, default=str), now()))


def load_case(break_id):
    row = _run("SELECT data FROM cases WHERE break_id = ?", (break_id,)).fetchone()
    return json.loads(row["data"]) if row else None


def case_statuses():
    return {r["break_id"]: r["status"] for r in _run("SELECT break_id, status FROM cases")}


# approval decisions and the gate's log

def put_decision(break_id, decision, approver, timestamp, notes):
    _run("INSERT INTO decisions VALUES (?, ?, ?, ?, ?) ON CONFLICT(break_id) DO UPDATE SET "
         "decision=excluded.decision, approver=excluded.approver, timestamp=excluded.timestamp, "
         "notes=excluded.notes", (break_id, decision, approver, timestamp, notes))


def get_decision(break_id):
    row = _run("SELECT decision, approver, timestamp, notes FROM decisions WHERE break_id = ?",
               (break_id,)).fetchone()
    return dict(row) if row else None


def log_gate(break_id, event, detail):
    _run("INSERT INTO gate_log (break_id, event, detail, timestamp) VALUES (?, ?, ?, ?)",
         (break_id, event, detail, now()))


def gate_events(break_id=None):
    sql = "SELECT break_id, event, detail, timestamp FROM gate_log"
    rows = _run(sql + " WHERE break_id = ? ORDER BY id", (break_id,)) if break_id else _run(sql + " ORDER BY id")
    return [dict(r) for r in rows]


# operational audit trail

def add_event(event):
    """Inserts one audit event. With a dedupe_key it is written at most once
    and the stored event is returned."""
    key = event.get("dedupe_key")
    with _LOCK:
        if key:
            row = _run("SELECT * FROM events WHERE dedupe_key = ?", (key,)).fetchone()
            if row:
                return _event(row)
        _run("INSERT INTO events (event_id, timestamp, actor_id, action, break_id, detail, source, metadata, dedupe_key) "
             "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
             (event["event_id"], event["timestamp"], event["actor_id"], event["action"], event["break_id"],
              event["detail"], event["source"], json.dumps(event["metadata"]), key))
    return event


def _event(row):
    e = dict(row)
    e["metadata"] = json.loads(e["metadata"] or "{}")
    e.pop("id", None)
    return e


def list_events(break_id=None, actor_id=None, action=None, limit=500):
    where, args = [], []
    for col, val in (("break_id", break_id), ("actor_id", actor_id), ("action", action)):
        if val:
            where.append(f"{col} = ?")
            args.append(val)
    sql = "SELECT * FROM events" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY id DESC LIMIT ?"
    return [_event(r) for r in _run(sql, (*args, limit))]


def reset(*tables):
    """Clears the given tables, or all of them. For tests and offline scripts only."""
    with _LOCK:
        for t in tables or ("cases", "decisions", "gate_log", "events"):
            _conn().execute(f"DELETE FROM {t}")
