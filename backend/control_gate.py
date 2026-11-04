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
Decisions and the gate's log are kept in SQLite (store.py), so they survive a
restart.
"""

import store
import auth


def _log(break_id, event, detail=""):
    store.log_gate(break_id, event, detail)


def record_decision(break_id, decision, approver, notes=None, actor_id=None):
    if decision not in ("APPROVE", "REJECT"):
        raise ValueError(f"decision must be APPROVE or REJECT, got {decision!r}")
    if actor_id is not None:
        try:
            auth.require_actor(actor_id, ("analyst", "approver"))
            auth.require_actor(approver, ("approver",))
            auth.require_distinct(actor_id, approver, "approver")
        except PermissionError as exc:
            raise ValueError(str(exc)) from exc
    store.put_decision(break_id, decision, approver, store.now(), notes)
    _log(break_id, f"HUMAN_DECISION:{decision}", f"by {approver}" + (f" - {notes}" if notes else ""))
    return store.get_decision(break_id)


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

    decision = store.get_decision(break_id)
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
    return store.get_decision(break_id)


def audit_trail(break_id=None):
    return store.gate_events(break_id)


def decision_history(break_id):
    return store.decision_history(break_id)


def reset():
    store.reset("decisions", "decision_history", "gate_log")
