"""Human-in-the-loop workflow for a case: start, approve, reject, escalate,
and the three-step manual path (start -> record action -> verify & close).

This used to live inside the Streamlit bridge, which meant nothing outside the
UI (the seeding script, tests) could drive a case the way an analyst does. It
has no Streamlit dependency: every function takes the acting Operations ID
explicitly, writes the case history, the operational audit trail and the
case store in one go.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "agents"))

import orchestrator  # noqa: E402
import control_gate  # noqa: E402
import case_store  # noqa: E402
import clock  # noqa: E402
from audit import record as audit  # noqa: E402

# Statuses from which a person can still choose how to resolve the break.
DECISION_STATUSES = {"CASE_CREATED", "IN_REVIEW", "AWAITING_APPROVAL", "ESCALATED"}
# Manual correction is also the way out of a reopened case (a failed automated fix,
# or a voluntary corporate action that needs an election recorded by a person).
MANUAL_START_STATUSES = DECISION_STATUSES | {"REOPENED"}
TERMINAL_STATUSES = {"CLOSED", "REJECTED"}


def _case(break_id):
    case = orchestrator.get_case(break_id)
    if case is None:
        raise KeyError(f"no case exists for {break_id} - start the case review first")
    return case


# Case-history events that the workflow functions below already write to the
# audit trail under the person's own Operations ID - mirroring them again as
# SYSTEM would show every human step twice.
_RECORDED_AS_HUMAN = {"EXECUTION_MODE", "HUMAN_IN_REVIEW", "HUMAN_ESCALATED", "MANUAL_RESOLUTION_STARTED",
                      "MANUAL_ACTION_SUBMITTED", "MANUAL_RESOLUTION_VERIFIED"}


def sync_case_audit(case):
    """Copy any system case-history entries not yet in the operational audit trail."""
    if not case:
        return
    bid = case["break_id"]
    history = case.get("history", [])
    start = int(case.get("_audit_synced", 0) or 0)
    if start >= len(history):
        return
    pairs = []
    for i in range(start, len(history)):
        e = history[i]
        if e.get("event") in _RECORDED_AS_HUMAN or (e.get("event") == "CASE_CLOSED"
                                                     and e.get("detail") == "manual resolution verified"):
            continue
        key = f"case:{bid}:history:{i}:{e.get('event')}:{e.get('timestamp')}"
        pairs.append(({"event_id": f"h{i:03d}{bid}", "timestamp": e.get("timestamp") or clock.now_iso(),
                       "actor_id": "SYSTEM", "action": e.get("event", "SYSTEM_EVENT"), "break_id": bid,
                       "detail": e.get("detail", ""), "source": "CASE_PIPELINE",
                       "metadata": {"dedupe_key": key}}, key))
    if pairs:
        case_store.insert_events(pairs)
    case["_audit_synced"] = len(history)
    orchestrator.save_case(case)


def get_case(break_id):
    case = orchestrator.get_case(break_id)
    sync_case_audit(case)
    return case


def start_case(break_id, actor, on_event=None):
    case = orchestrator.get_case(break_id)
    if case is None:
        audit(actor, "CASE_ANALYSIS_STARTED", break_id, "Analyst started the case pipeline")
        case = orchestrator.create_case(break_id, on_event=on_event)
        if case["status"] == "CLOSED":
            # PROPOSAL-tier fixes are administrative and authorized by policy, so the
            # pipeline closes them without a sign-off. Say so explicitly in the trail.
            case["resolution_mode"] = "Policy (no approval required)"
            orchestrator.save_case(case)
    sync_case_audit(case)
    return case


def resume_case(break_id, on_event=None):
    case = orchestrator.resume_case(break_id, on_event=on_event)
    sync_case_audit(case)
    return case


def approve(break_id, approver, notes=None, mode="Assisted", on_event=None):
    case = _case(break_id)
    audit(approver, "APPROVAL_GRANTED", break_id,
          f"Approved by {approver}; execution mode: {mode}; notes: {notes or '-'}")
    control_gate.record_decision(break_id, "APPROVE", approver, f"[{mode}] {notes or ''}".strip())
    case["execution_mode"] = mode
    case["resolution_mode"] = f"{mode} (approved by {approver})"
    orchestrator._log(case, "EXECUTION_MODE", mode)
    audit(approver, "CONTROLLED_ACTION_SELECTED", break_id, f"Execution mode: {mode}")
    return resume_case(break_id, on_event=on_event)


def mark(break_id, status, actor, notes=None):
    """Non-final human choices: IN_REVIEW or ESCALATED. The gate stays closed."""
    if status not in ("IN_REVIEW", "ESCALATED"):
        raise ValueError(f"mark() only records IN_REVIEW or ESCALATED, got {status}")
    case = _case(break_id)
    audit(actor, "CASE_ESCALATED" if status == "ESCALATED" else "CASE_REVIEWED", break_id,
          f"{status} by {actor}; notes: {notes or '-'}")
    case["status"] = status
    orchestrator._log(case, "HUMAN_" + status, f"by {actor}: {notes or ''}".strip())
    sync_case_audit(case)
    return case


def reject(break_id, approver, notes=None):
    _case(break_id)
    audit(approver, "APPROVAL_REJECTED", break_id, f"Rejected by {approver}; notes: {notes or '-'}")
    control_gate.record_decision(break_id, "REJECT", approver, notes)
    return resume_case(break_id)


def begin_manual(break_id, operator, notes=""):
    """Start a manual resolution. This is an execution choice, not an approval,
    and never closes the case: the break stays open while the analyst makes the
    correction in the owning operational system."""
    case = _case(break_id)
    if case.get("status") not in MANUAL_START_STATUSES:
        raise ValueError(f"a manual resolution can't be started from status {case.get('status')}")
    case["execution_mode"] = "Manual"
    case["status"] = "MANUAL_IN_PROGRESS"
    case["manual_resolution"] = {"operator": operator, "started_at": clock.now_iso(), "notes": notes,
                                 "actions": [], "evidence": []}
    orchestrator._log(case, "MANUAL_RESOLUTION_STARTED", f"by {operator}: {notes or 'manual correction started'}")
    audit(operator, "MANUAL_RESOLUTION_STARTED", break_id,
          f"Manual resolution started by {operator}; {notes or 'no note'}")
    sync_case_audit(case)
    return case


def submit_manual(break_id, operator, action_taken, evidence_reference, checklist):
    """Record the human-performed correction and move to verification. Does not
    call the execution simulator and does not close the case."""
    case = _case(break_id)
    if case.get("status") != "MANUAL_IN_PROGRESS":
        raise ValueError("manual resolution has not been started")
    if not (action_taken or "").strip():
        raise ValueError("describe the action performed before submitting")
    if not (evidence_reference or "").strip():
        raise ValueError("provide a confirmation or evidence reference")
    if not checklist or not all(checklist):
        raise ValueError("complete every required evidence check before submitting")
    case["manual_resolution"].update({"submitted_by": operator, "submitted_at": clock.now_iso(),
                                      "action_taken": action_taken, "evidence_reference": evidence_reference,
                                      "checklist": list(checklist)})
    case["status"] = "AWAITING_VERIFICATION"
    orchestrator._log(case, "MANUAL_ACTION_SUBMITTED", f"by {operator}; evidence={evidence_reference}")
    audit(operator, "MANUAL_ACTION_SUBMITTED", break_id,
          f"Manual correction recorded by {operator}; evidence/reference: {evidence_reference}")
    sync_case_audit(case)
    return case


def verify_manual(break_id, verifier, verification_notes):
    """Close a manually resolved case only after a separate (four-eyes) verification."""
    case = _case(break_id)
    if case.get("status") != "AWAITING_VERIFICATION":
        raise ValueError("case is not awaiting verification")
    verifier = (verifier or "").strip().upper()
    if not verifier:
        raise ValueError("enter the verifier's Operations ID")
    submitter = (case["manual_resolution"].get("submitted_by") or "").strip().upper()
    if verifier == submitter:
        raise ValueError(f"verification must be done by someone other than {submitter}, "
                         "who recorded the correction (four-eyes check)")
    if not (verification_notes or "").strip():
        raise ValueError("verification notes are required")
    mr = case["manual_resolution"]
    mr.update({"verified_by": verifier, "verified_at": clock.now_iso(), "verification_notes": verification_notes})
    case["status"] = "CLOSED"
    case["resolution_mode"] = f"Manual (by {mr.get('submitted_by')}, verified by {verifier})"
    orchestrator._log(case, "MANUAL_RESOLUTION_VERIFIED", f"verified by {verifier}: {verification_notes}")
    orchestrator._log(case, "CASE_CLOSED", "manual resolution verified")
    audit(verifier, "MANUAL_RESOLUTION_VERIFIED", break_id, f"Verified by {verifier}: {verification_notes}")
    audit(verifier, "CASE_CLOSED", break_id, "Case closed after independent manual-resolution verification")
    sync_case_audit(case)
    return case


def resolution_record(case):
    """Who closed the case, when and how - for the 'Resolution record' card."""
    if not case or case.get("status") != "CLOSED":
        return None
    closed_at = next((e["timestamp"] for e in reversed(case.get("history", []))
                      if e["event"] == "CASE_CLOSED"), None)
    decision = control_gate.get_decision(case["break_id"]) or {}
    mr = case.get("manual_resolution") or {}
    if mr.get("verified_by"):
        how, by = "Manual correction, independently verified", f"{mr.get('submitted_by')} -> verified by {mr['verified_by']}"
    elif decision.get("decision") == "APPROVE":
        how, by = "Controlled action, approved and validated", decision.get("approver")
    else:
        how, by = "Administrative fix authorized by policy, validated", "SYSTEM (policy)"
    return {"closed_at": closed_at, "how": how, "by": by,
            "validation": (case.get("validation") or {}).get("reason") or mr.get("verification_notes"),
            "evidence_reference": mr.get("evidence_reference")}


def status_counts():
    from collections import Counter
    return Counter(c.get("status", "") for c in orchestrator._CASES.values())


def reset_demo():
    """Discard everything done live and go back to the committed seed state."""
    case_store.reset_to_seed()
    orchestrator.reload()
    control_gate.reload()
