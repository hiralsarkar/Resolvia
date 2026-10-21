"""
Control Gate - the wall between "recommendation" and "execution" that
the whole project is organized around. Not an agent - deterministic
policy enforcement. The orchestrator cannot decide that
approval is unnecessary for an action that policy says requires
approval.

Logic:
  - authority_tier == "PROPOSAL": administrative-only, authorized by
    policy without requiring a recorded human decision (still logged,
    still visible in the audit trail, just not gated behind formal
    sign-off - see resolution.py's docstring for why this split exists).
  - authority_tier == "CONTROLLED_ACTION": requires an explicit APPROVE
    decision recorded for this break_id BEFORE execution is authorized.
    No decision, or a REJECT decision, both result in a BLOCKED
    execution - the case stays open, nothing gets touched.

record_decision() is the only way a human enters the loop here - there
is no code path in this module that can set its own approval.
"""

import case_store
import clock

# Both are mirrored to the case store on every write and reloaded on import,
# so an approval recorded before a restart still authorizes execution after it.
_DECISIONS = case_store.load_decisions()  # break_id -> {"decision", "approver", "timestamp", "notes"}
_AUDIT_LOG = case_store.load_gate_events()  # append-only list of {break_id, event, detail, timestamp}


def _log(break_id, event, detail=""):
    e = {"break_id": break_id, "event": event, "detail": detail, "timestamp": clock.now_iso()}
    _AUDIT_LOG.append(e)
    case_store.append_gate_event(e)


def record_decision(break_id, decision, approver, notes=None):
    """The ONLY human-entry point in this module. decision must be
    APPROVE or REJECT."""
    if decision not in ("APPROVE", "REJECT"):
        raise ValueError(f"decision must be APPROVE or REJECT, got {decision!r}")
    _DECISIONS[break_id] = {"decision": decision, "approver": approver,
                             "timestamp": clock.now_iso(), "notes": notes}
    case_store.save_decision(break_id, _DECISIONS[break_id])
    _log(break_id, f"HUMAN_DECISION:{decision}", f"by {approver}" + (f" - {notes}" if notes else ""))
    return _DECISIONS[break_id]


def check_gate(proposal):
    """Returns {"authorized": bool, "reason": str}. Never mutates
    anything - purely a policy check the caller must obey before
    calling execution_simulator.execute()."""
    break_id = proposal["break_id"]

    # An administrative fix only skips sign-off when the diagnosis behind it is
    # trustworthy. If RCA itself said a person must confirm the root cause
    # (low model confidence, or a corporate action), the "it's only admin" shortcut
    # would let a possibly-wrong diagnosis execute unseen - so it needs approval too.
    needs_review = bool(proposal.get("rca_flagged_for_human_review"))
    if proposal["authority_tier"] == "PROPOSAL" and not needs_review:
        result = {"authorized": True, "reason": "PROPOSAL tier - administrative action, "
                  "authorized by policy without requiring formal sign-off"}
        _log(break_id, "GATE_CHECK:AUTHORIZED", result["reason"])
        return result

    decision = _DECISIONS.get(break_id)
    if decision is None:
        why = ("CONTROLLED_ACTION requires" if proposal["authority_tier"] != "PROPOSAL" else
               "the root-cause diagnosis was flagged for human review, so this administrative fix requires")
        result = {"authorized": False,
                   "reason": f"BLOCKED - {why} an explicit human APPROVE "
                             "decision before execution; none has been recorded"}
        _log(break_id, "GATE_CHECK:BLOCKED", result["reason"])
        return result

    if decision["decision"] == "APPROVE":
        result = {"authorized": True,
                   "reason": f"AUTHORIZED - approved by {decision['approver']} at {decision['timestamp']}"}
        _log(break_id, "GATE_CHECK:AUTHORIZED", result["reason"])
        return result

    result = {"authorized": False,
               "reason": f"BLOCKED - REJECTED by {decision['approver']}" +
                         (f": {decision['notes']}" if decision.get("notes") else "")}
    _log(break_id, "GATE_CHECK:BLOCKED", result["reason"])
    return result


def get_decision(break_id):
    """Lets a caller (the Orchestrator) distinguish 'no decision yet'
    (None) from a terminal REJECT - those need different case states,
    not the same generic 'not authorized' bucket."""
    return _DECISIONS.get(break_id)


def audit_trail(break_id=None):
    if break_id is None:
        return list(_AUDIT_LOG)
    return [e for e in _AUDIT_LOG if e["break_id"] == break_id]


def reload():
    """Re-read decisions and the gate log from the case store."""
    _DECISIONS.clear()
    _DECISIONS.update(case_store.load_decisions())
    _AUDIT_LOG[:] = case_store.load_gate_events()


def reset():
    """Test/demo helper - clears all decisions and audit log. Detaches from the
    saved database first, so smoke tests and evals never wipe real case history."""
    case_store.use_memory()
    _DECISIONS.clear()
    _AUDIT_LOG.clear()
