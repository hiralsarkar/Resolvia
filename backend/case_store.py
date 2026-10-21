"""Durable state for Resolvia: cases, approvals, gate log, audit trail and
supplemental evidence, all in one SQLite file.

Before this module everything lived in Python dicts, so a server restart (or a
Streamlit Cloud reboot) silently reopened every break and wiped the case
histories. Now each write lands on disk immediately and the orchestrator,
control gate and audit log reload from here on import.

Files
  backend/db/resolvia.db              the live database (git-ignored, written by the app)
  backend/db/seed/resolvia_seed.db    committed starting point: ~25% of breaks already
                                      worked through the real pipeline with full audit
                                      trails (built by backend/db/seed_cases.py)

On first start the live database is copied from the seed, so a fresh clone opens
with history already in place. Set RESOLVIA_DB to point somewhere else.

Tests, evals and smoke scripts call orchestrator.reset()/control_gate.reset(),
which switch this module to an in-memory database first, so they never
touch the saved cases.
"""

import json
import os
import shutil
import sqlite3
import threading
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(HERE, "db")
DEFAULT_DB_PATH = os.environ.get("RESOLVIA_DB") or os.path.join(DB_DIR, "resolvia.db")
SEED_DB_PATH = os.path.join(DB_DIR, "seed", "resolvia_seed.db")
LEGACY_AUDIT_JSON = os.path.join(HERE, "knowledge", "operational_audit.json")

_LOCK = threading.RLock()
_CONN = None
_PATH = None  # path currently open, ":memory:" when detached

_SCHEMA = """
CREATE TABLE IF NOT EXISTS cases (
    break_id   TEXT PRIMARY KEY,
    status     TEXT NOT NULL,
    updated_at TEXT,
    data       BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS decisions (
    break_id  TEXT PRIMARY KEY,
    decision  TEXT NOT NULL,
    approver  TEXT,
    timestamp TEXT,
    notes     TEXT
);
CREATE TABLE IF NOT EXISTS gate_audit (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    break_id  TEXT,
    event     TEXT,
    detail    TEXT,
    timestamp TEXT
);
CREATE TABLE IF NOT EXISTS audit_events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id   TEXT NOT NULL,
    timestamp  TEXT NOT NULL,
    actor_id   TEXT NOT NULL,
    action     TEXT NOT NULL,
    break_id   TEXT NOT NULL DEFAULT '',
    detail     TEXT NOT NULL DEFAULT '',
    source     TEXT NOT NULL DEFAULT '',
    metadata   TEXT NOT NULL DEFAULT '{}',
    dedupe_key TEXT UNIQUE
);
CREATE INDEX IF NOT EXISTS ix_audit_break ON audit_events(break_id);
CREATE INDEX IF NOT EXISTS ix_audit_ts ON audit_events(timestamp);
CREATE TABLE IF NOT EXISTS supplemental (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    break_id   TEXT NOT NULL,
    kind       TEXT NOT NULL,          -- 'document' | 'review'
    created_at TEXT,
    payload    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_supp_break ON supplemental(break_id, kind);
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);
"""


def _json_default(o):
    if hasattr(o, "item"):          # numpy scalars
        return o.item()
    if hasattr(o, "tolist"):        # numpy arrays
        return o.tolist()
    if hasattr(o, "isoformat"):     # datetimes / pandas Timestamps
        return o.isoformat()
    return str(o)


def dumps(obj):
    return json.dumps(obj, default=_json_default, ensure_ascii=False)


def _open(path):
    global _CONN, _PATH
    if _CONN is not None:
        try:
            _CONN.close()
        except sqlite3.Error:
            pass
    if path != ":memory:":
        os.makedirs(os.path.dirname(path), exist_ok=True)
        if not os.path.exists(path) and os.path.exists(SEED_DB_PATH) and \
                os.path.abspath(path) != os.path.abspath(SEED_DB_PATH):
            shutil.copyfile(SEED_DB_PATH, path)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(_SCHEMA)
    _CONN, _PATH = conn, path
    if path != ":memory:":
        _migrate_legacy_audit()
    return conn


def _conn():
    with _LOCK:
        if _CONN is None:
            _open(DEFAULT_DB_PATH)
        return _CONN


def path():
    _conn()
    return _PATH


def is_persistent():
    return path() != ":memory:"


def use_memory():
    """Detach from the saved database (tests, evals, smoke scripts)."""
    with _LOCK:
        if _PATH != ":memory:" or _CONN is None:
            _open(":memory:")


def use_path(db_path):
    """Open a specific database file (the seeder writes the seed file directly)."""
    with _LOCK:
        _open(db_path)


def reset_to_seed():
    """Throw away live changes and start again from the committed seed."""
    with _LOCK:
        target = DEFAULT_DB_PATH
        if _CONN is not None:
            _CONN.close()
        for suffix in ("", "-wal", "-shm"):
            p = target + suffix
            if os.path.exists(p):
                os.remove(p)
        _open(target)


def wipe():
    with _LOCK:
        c = _conn()
        for t in ("cases", "decisions", "gate_audit", "audit_events", "supplemental", "meta"):
            c.execute(f"DELETE FROM {t}")


# ---------------------------------------------------------------- cases

def save_case(case):
    blob = zlib.compress(dumps(case).encode("utf-8"), 6)
    updated = case["history"][-1]["timestamp"] if case.get("history") else None
    with _LOCK:
        _conn().execute(
            "INSERT INTO cases(break_id, status, updated_at, data) VALUES (?,?,?,?) "
            "ON CONFLICT(break_id) DO UPDATE SET status=excluded.status, "
            "updated_at=excluded.updated_at, data=excluded.data",
            (case["break_id"], case.get("status", ""), updated, blob))


def load_cases():
    with _LOCK:
        rows = _conn().execute("SELECT data FROM cases").fetchall()
    out = {}
    for r in rows:
        case = json.loads(zlib.decompress(r["data"]).decode("utf-8"))
        out[case["break_id"]] = case
    return out


def delete_case(break_id):
    with _LOCK:
        _conn().execute("DELETE FROM cases WHERE break_id=?", (break_id,))


# ---------------------------------------------------------------- control gate

def save_decision(break_id, d):
    with _LOCK:
        _conn().execute(
            "INSERT INTO decisions(break_id, decision, approver, timestamp, notes) VALUES (?,?,?,?,?) "
            "ON CONFLICT(break_id) DO UPDATE SET decision=excluded.decision, approver=excluded.approver, "
            "timestamp=excluded.timestamp, notes=excluded.notes",
            (break_id, d["decision"], d.get("approver"), d.get("timestamp"), d.get("notes")))


def load_decisions():
    with _LOCK:
        rows = _conn().execute("SELECT * FROM decisions").fetchall()
    return {r["break_id"]: {"decision": r["decision"], "approver": r["approver"],
                            "timestamp": r["timestamp"], "notes": r["notes"]} for r in rows}


def append_gate_event(e):
    with _LOCK:
        _conn().execute("INSERT INTO gate_audit(break_id, event, detail, timestamp) VALUES (?,?,?,?)",
                        (e["break_id"], e["event"], e["detail"], e["timestamp"]))


def load_gate_events():
    with _LOCK:
        rows = _conn().execute("SELECT break_id, event, detail, timestamp FROM gate_audit ORDER BY id").fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- operational audit

def _row_to_event(r):
    e = dict(r)
    e.pop("id", None)
    dk = e.pop("dedupe_key", None)
    try:
        e["metadata"] = json.loads(e.get("metadata") or "{}")
    except json.JSONDecodeError:
        e["metadata"] = {}
    if dk:
        e["metadata"].setdefault("dedupe_key", dk)
    return e


def insert_event(event, dedupe_key=None):
    """Append one audit event. With a dedupe_key, a repeat is ignored and the
    original event is returned instead."""
    with _LOCK:
        c = _conn()
        cur = c.execute(
            "INSERT OR IGNORE INTO audit_events(event_id, timestamp, actor_id, action, break_id, detail, "
            "source, metadata, dedupe_key) VALUES (?,?,?,?,?,?,?,?,?)",
            (event["event_id"], event["timestamp"], event["actor_id"], event["action"], event["break_id"],
             event["detail"], event["source"], dumps(event.get("metadata") or {}), dedupe_key))
        if cur.rowcount == 0 and dedupe_key:
            r = c.execute("SELECT * FROM audit_events WHERE dedupe_key=?", (dedupe_key,)).fetchone()
            return _row_to_event(r) if r else event
    return event


def insert_events(events):
    """Bulk insert of (event, dedupe_key) pairs in one transaction."""
    with _LOCK:
        c = _conn()
        c.execute("BEGIN")
        try:
            c.executemany(
                "INSERT OR IGNORE INTO audit_events(event_id, timestamp, actor_id, action, break_id, detail, "
                "source, metadata, dedupe_key) VALUES (?,?,?,?,?,?,?,?,?)",
                [(e["event_id"], e["timestamp"], e["actor_id"], e["action"], e["break_id"], e["detail"],
                  e["source"], dumps(e.get("metadata") or {}), k) for e, k in events])
            c.execute("COMMIT")
        except Exception:
            c.execute("ROLLBACK")
            raise


def _where(break_id=None, actor_id=None, action=None, break_ids=None, actor_ids=None, actions=None):
    clauses, args = [], []
    for col, single, many in (("break_id", break_id, break_ids), ("actor_id", actor_id, actor_ids),
                              ("action", action, actions)):
        if single:
            clauses.append(f"{col}=?"); args.append(single)
        if many:
            clauses.append(f"{col} IN ({','.join('?' * len(many))})"); args.extend(many)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", args


def query_events(limit=500, offset=0, newest_first=True, **filters):
    where, args = _where(**filters)
    order = "DESC" if newest_first else "ASC"
    sql = f"SELECT * FROM audit_events{where} ORDER BY timestamp {order}, id {order} LIMIT ? OFFSET ?"
    with _LOCK:
        rows = _conn().execute(sql, args + [int(limit), int(offset)]).fetchall()
    return [_row_to_event(r) for r in rows]


def count_events(**filters):
    where, args = _where(**filters)
    with _LOCK:
        return _conn().execute(f"SELECT COUNT(*) FROM audit_events{where}", args).fetchone()[0]


def event_stats(**filters):
    where, args = _where(**filters)
    sql = (f"SELECT COUNT(*) total, SUM(actor_id!='SYSTEM') human, "
           f"SUM(action='APPROVAL_GRANTED') approvals, SUM(action='CASE_ESCALATED') escalations, "
           f"COUNT(DISTINCT NULLIF(break_id,'')) breaks FROM audit_events{where}")
    with _LOCK:
        r = _conn().execute(sql, args).fetchone()
    total = r["total"] or 0
    human = r["human"] or 0
    return {"total": total, "human": human, "system": total - human,
            "approvals": r["approvals"] or 0, "escalations": r["escalations"] or 0,
            "breaks": r["breaks"] or 0}


def distinct_values(column):
    if column not in ("actor_id", "action", "break_id", "source"):
        raise ValueError(column)
    with _LOCK:
        rows = _conn().execute(f"SELECT DISTINCT {column} FROM audit_events WHERE {column}!='' "
                               f"ORDER BY {column}").fetchall()
    return [r[0] for r in rows]


def _migrate_legacy_audit():
    """One-off import of the old JSON audit log, if it exists and hasn't been imported."""
    c = _CONN
    done = c.execute("SELECT value FROM meta WHERE key='legacy_audit_imported'").fetchone()
    if done or not os.path.exists(LEGACY_AUDIT_JSON):
        return
    try:
        with open(LEGACY_AUDIT_JSON, encoding="utf-8") as f:
            events = json.load(f)
    except (OSError, json.JSONDecodeError):
        events = []
    pairs = []
    for e in events if isinstance(events, list) else []:
        md = e.get("metadata") or {}
        pairs.append(({"event_id": e.get("event_id", ""), "timestamp": e.get("timestamp", ""),
                       "actor_id": e.get("actor_id", "SYSTEM"), "action": e.get("action", ""),
                       "break_id": e.get("break_id", ""), "detail": e.get("detail", ""),
                       "source": e.get("source", "UI"), "metadata": md}, md.get("dedupe_key")))
    if pairs:
        insert_events(pairs)
    c.execute("INSERT OR REPLACE INTO meta(key, value) VALUES ('legacy_audit_imported', '1')")


# ---------------------------------------------------------------- supplemental evidence

def add_supplemental(break_id, kind, payload, created_at=None):
    with _LOCK:
        _conn().execute("INSERT INTO supplemental(break_id, kind, created_at, payload) VALUES (?,?,?,?)",
                        (break_id, kind, created_at, dumps(payload)))


def list_supplemental(break_id, kind):
    with _LOCK:
        rows = _conn().execute("SELECT payload FROM supplemental WHERE break_id=? AND kind=? ORDER BY id",
                               (break_id, kind)).fetchall()
    return [json.loads(r["payload"]) for r in rows]


# ---------------------------------------------------------------- meta

def set_meta(key, value):
    with _LOCK:
        _conn().execute("INSERT OR REPLACE INTO meta(key, value) VALUES (?,?)", (key, dumps(value)))


def get_meta(key, default=None):
    with _LOCK:
        r = _conn().execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
    return json.loads(r["value"]) if r else default
