"""
Control Gate: the line between a recommendation and an action.

This is policy code, not an agent and not a model. The Orchestrator has to ask
it before anything is executed and has to obey the answer.

The rule:
  - A proposal that needs no approval (an administrative PROPOSAL-tier step on
    a diagnosis nobody flagged) is authorised by policy. It is still logged.
  - Everything else needs an APPROVE decision recorded against that break.
    That covers every CONTROLLED_ACTION, plus any action whose diagnosis RCA
    flagged for a person (corporate actions, low confidence).
    No decision, or a REJECT, means blocked. The case stays open and nothing
    is touched.

record_decision() is the only way a person's decision gets in. Nothing in this
module, or anywhere else in the backend, can approve on its own behalf.
"""

from datetime import datetime, timezone

_DECISIONS = {}  # break_id -> {"decision", "approver", "timestamp", "notes"}
_AUDIT_LOG = []  # append only


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(break_id, event, detail=""):
    _AUDIT_LOG.append({"break_id": break_id, "event": event, "detail": detail, "timestamp": _now()})


def record_decision(break_id, decision, approver, notes=None):
    if decision not in ("APPROVE", "REJECT"):
        raise ValueError(f"decision must be APPROVE or REJECT, got {decision!r}")
    _DECISIONS[break_id] = {"decision": decision, "approver": approver, "timestamp": _now(), "notes": notes}
    _log(break_id, f"HUMAN_DECISION:{decision}", f"by {approver}" + (f" - {notes}" if notes else ""))
    return _DECISIONS[break_id]


def needs_approval(proposal):
    if "approval_required" in proposal:
        return bool(proposal["approval_required"])
    return proposal["authority_tier"] != "PROPOSAL"


def check_gate(proposal):
    """Returns {"authorized": bool, "reason": str}. Changes nothing."""
    break_id = proposal["break_id"]

    if not needs_approval(proposal):
        result = {"authorized": True,
                  "reason": "administrative step on an unflagged diagnosis, authorised by policy"}
        _log(break_id, "GATE_CHECK:AUTHORIZED", result["reason"])
        return result

    decision = _DECISIONS.get(break_id)
    if decision is None:
        why = "a controlled action" if proposal["authority_tier"] == "CONTROLLED_ACTION" \
            else "a diagnosis flagged for review"
        result = {"authorized": False,
                  "reason": f"BLOCKED - {why} needs a recorded APPROVE and there isn't one yet"}
    elif decision["decision"] == "APPROVE":
        result = {"authorized": True,
                  "reason": f"AUTHORIZED - approved by {decision['approver']} at {decision['timestamp']}"}
    else:
        result = {"authorized": False,
                  "reason": f"BLOCKED - rejected by {decision['approver']}"
                            + (f": {decision['notes']}" if decision.get("notes") else "")}

    _log(break_id, "GATE_CHECK:" + ("AUTHORIZED" if result["authorized"] else "BLOCKED"), result["reason"])
    return result


def get_decision(break_id):
    """None means nobody has decided yet, which is different from a REJECT."""
    return _DECISIONS.get(break_id)


def audit_trail(break_id=None):
    if break_id is None:
        return list(_AUDIT_LOG)
    return [e for e in _AUDIT_LOG if e["break_id"] == break_id]


def reset():
    _DECISIONS.clear()
    _AUDIT_LOG.clear()
