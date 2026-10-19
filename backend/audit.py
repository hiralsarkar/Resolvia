"""
Operational audit log.

Every human and system action the app records: who did what, to which break,
and when. Events go into the SQLite database (store.py), so the trail
survives restarts and can be filtered by break, person or action.
"""

from uuid import uuid4

import store


def record(actor_id, action, break_id=None, detail="", source="UI", metadata=None, dedupe_key=None):
    event = {
        "event_id": uuid4().hex[:12],
        "timestamp": store.now(),
        "actor_id": actor_id or "SYSTEM",
        "action": action,
        "break_id": break_id or "",
        "detail": detail or "",
        "source": source,
        "metadata": metadata or {},
        "dedupe_key": dedupe_key,
    }
    return store.add_event(event)


def list_events(break_id=None, actor_id=None, action=None, limit=500):
    """Newest first."""
    return store.list_events(break_id, actor_id, action, limit)


def summary():
    events = list_events(limit=1_000_000)
    human = [e for e in events if e.get("actor_id") != "SYSTEM"]
    return {
        "total": len(events),
        "human": len(human),
        "system": len(events) - len(human),
        "approvals": sum(1 for e in events if e.get("action") == "APPROVAL_GRANTED"),
        "escalations": sum(1 for e in events if e.get("action") == "CASE_ESCALATED"),
    }
