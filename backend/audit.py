"""Operational audit logging for Resolvia.

Keeps a lightweight local JSON event log so the UI can show human and system
activity without introducing a database dependency for the demo deployment.
"""
import json
import os
import threading
from datetime import datetime, timezone
from uuid import uuid4

_HERE = os.path.dirname(os.path.abspath(__file__))
_PATH = os.path.join(_HERE, "knowledge", "operational_audit.json")
_LOCK = threading.Lock()
_MAX_EVENTS = 10000


def _load():
    try:
        with open(_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def record(actor_id, action, break_id=None, detail="", source="UI", metadata=None, dedupe_key=None):
    event = {
        "event_id": uuid4().hex[:12],
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "actor_id": actor_id or "SYSTEM",
        "action": action,
        "break_id": break_id or "",
        "detail": detail or "",
        "source": source,
        "metadata": metadata or {},
    }
    with _LOCK:
        events = _load()
        if dedupe_key and any(e.get("metadata", {}).get("dedupe_key") == dedupe_key for e in events):
            return next(e for e in events if e.get("metadata", {}).get("dedupe_key") == dedupe_key)
        if dedupe_key:
            event["metadata"]["dedupe_key"] = dedupe_key
        events.append(event)
        events = events[-_MAX_EVENTS:]
        try:
            os.makedirs(os.path.dirname(_PATH), exist_ok=True)
            with open(_PATH, "w", encoding="utf-8") as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
        except OSError:
            pass
    return event


def list_events(break_id=None, actor_id=None, action=None, limit=500):
    with _LOCK:
        events = _load()
    if break_id:
        events = [e for e in events if e.get("break_id") == break_id]
    if actor_id:
        events = [e for e in events if e.get("actor_id") == actor_id]
    if action:
        events = [e for e in events if e.get("action") == action]
    return list(reversed(events[-limit:]))


def summary():
    events = list_events(limit=_MAX_EVENTS)
    human = [e for e in events if e.get("actor_id") != "SYSTEM"]
    return {
        "total": len(events),
        "human": len(human),
        "system": len(events) - len(human),
        "approvals": sum(1 for e in events if e.get("action") == "APPROVAL_GRANTED"),
        "escalations": sum(1 for e in events if e.get("action") == "CASE_ESCALATED"),
    }
