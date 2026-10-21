"""Operational audit logging for Resolvia.

Every human action and system event is written to the `audit_events` table in
the case store (backend/case_store.py), so the trail survives page reloads and
server restarts. The previous JSON file log (knowledge/operational_audit.json)
is imported once automatically if it exists.

The table is append-only from the application's point of view: nothing in the
app edits or deletes an event.
"""
from uuid import uuid4

import case_store
import clock


def record(actor_id, action, break_id=None, detail="", source="UI", metadata=None, dedupe_key=None,
           timestamp=None):
    event = {
        "event_id": uuid4().hex[:12],
        "timestamp": timestamp or clock.now_iso(),
        "actor_id": actor_id or "SYSTEM",
        "action": action,
        "break_id": break_id or "",
        "detail": detail or "",
        "source": source,
        "metadata": dict(metadata or {}),
    }
    if dedupe_key:
        event["metadata"]["dedupe_key"] = dedupe_key
    return case_store.insert_event(event, dedupe_key=dedupe_key)


def list_events(break_id=None, actor_id=None, action=None, limit=500, offset=0,
                break_ids=None, actor_ids=None, actions=None):
    """Newest first."""
    return case_store.query_events(limit=limit, offset=offset, break_id=break_id, actor_id=actor_id,
                                   action=action, break_ids=break_ids, actor_ids=actor_ids, actions=actions)


def count(**filters):
    return case_store.count_events(**filters)


def distinct(column):
    return case_store.distinct_values(column)


def summary(**filters):
    return case_store.event_stats(**filters)
