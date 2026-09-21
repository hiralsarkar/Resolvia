"""
Orchestrator.

"The orchestrator is not another intelligent agent that makes financial
decisions. It is the workflow controller." State machine:

  CASE CREATED -> TRIAGE -> INVESTIGATION -> RCA -> RESOLUTION PROPOSAL
  -> HUMAN CONTROL -> [blocked | authorized] -> CONTROLLED ACTION
  -> VALIDATION -> CLOSE/REOPEN -> AUDIT

Two-phase because a real system can't synchronously block waiting for a
human: create_case() runs every automatic stage in order and stops the
moment it hits an unauthorized CONTROLLED_ACTION - the case sits in
AWAITING_APPROVAL until someone calls control_gate.record_decision()
externally, then resume_case() picks up exactly where it left off.
Nothing in this module can itself set a decision or skip the gate check
- "the orchestrator cannot decide that approval is unnecessary for an
action that policy says requires approval" (architecture discussion,
Section 7). It only calls through to control_gate and obeys the answer.

Every case keeps a full history (audit log) of stage transitions,
separate from control_gate's own gate-only audit log - this one covers
the whole pipeline (Triage's routing decision, RCA's diagnosis, the
proposal itself), not just approval events.
"""

import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "agents"))
sys.path.insert(0, HERE)

import triage  # noqa: E402
import investigation  # noqa: E402
import rca  # noqa: E402
import resolution  # noqa: E402
import control_gate  # noqa: E402
import execution_simulator  # noqa: E402
from validation import validate  # noqa: E402

_CASES = {}  # break_id -> case state dict


def _log(case, event, detail=""):
    case["history"].append({
        "event": event, "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    })


def _new_case(break_id):
    return {
        "break_id": break_id, "status": "CASE_CREATED", "history": [],
        "triage": None, "investigation": None, "rca": None, "proposal": None,
        "gate_result": None, "post_execution": None, "validation": None,
    }


def _advance(case, on_event=None):
    """Runs every stage the case hasn't completed yet, stopping at the
    first thing it can't get past on its own (a data-quality halt, or
    an unauthorized CONTROLLED_ACTION). Safe to call repeatedly - each
    stage only runs once (guarded by `is None`), so resume_case() just
    calls this again and it naturally continues from wherever it
    stopped.

    `on_event(stage_key, label, detail)` is an optional callback fired
    right after each real stage completes - a UI hook only (the frontend
    uses it to show genuine per-agent progress synced to actual
    execution, not a fake animation timed independently of it). Never
    required, never changes control flow."""
    break_id = case["break_id"]

    def fire(stage_key, label, detail):
        if on_event:
            on_event(stage_key, label, detail)

    if case["triage"] is None:
        case["triage"] = triage.triage(break_id)
        t = case["triage"]
        _log(case, "TRIAGE_COMPLETE",
             f"family={t['predicted_family']} priority={t['priority']} route={t['route']}")
        fire("triage", "Triage Agent", f"routed to {t['route']}, priority {t['priority']}")
        if not t["valid"]:
            case["status"] = "HALTED_DATA_QUALITY"
            _log(case, "CASE_HALTED", "; ".join(t["validation_issues"]))
            return case

    if case["investigation"] is None:
        case["investigation"] = investigation.investigate(break_id)
        doc = case["investigation"]["document_evidence"]
        _log(case, "INVESTIGATION_COMPLETE", f"has_document={doc.get('has_document', False)}")
        fire("investigation", "Investigation Agent",
             "evidence gathered" + (", document retrieved" if doc.get("has_document") else ""))

    if case["rca"] is None:
        case["rca"] = rca.analyze(break_id)
        r = case["rca"]
        _log(case, "RCA_COMPLETE",
             f"root_cause={r['root_cause']} confidence={r['confidence']:.2f} "
             f"requires_human_decision={r['requires_human_decision']}")
        fire("rca", "RCA Agent", f"{r['root_cause']} at {r['confidence']*100:.1f}% confidence")

    if case["proposal"] is None:
        case["proposal"] = resolution.propose(break_id)
        p = case["proposal"]
        _log(case, "RESOLUTION_PROPOSAL_COMPLETE",
             f"action={p['recommended_action'][:70]!r} authority_tier={p['authority_tier']}")
        fire("proposal", "Resolution Proposal Agent", p["authority_tier"].replace("_", " "))

    gate_result = control_gate.check_gate(case["proposal"])
    case["gate_result"] = gate_result
    _log(case, "GATE_CHECK:" + ("AUTHORIZED" if gate_result["authorized"] else "BLOCKED"),
         gate_result["reason"])
    # This fire is deliberately attributed to "Orchestrator", not an agent -
    # control_gate.check_gate() is a fixed policy lookup; deciding what to
    # DO with that answer (halt the case vs. proceed to execution) is the
    # one real branching decision the Orchestrator itself makes per run.
    fire("gate", "Orchestrator", "gate authorized - proceeding" if gate_result["authorized"]
         else "gate blocked - halting for human approval")

    if not gate_result["authorized"]:
        decision = control_gate.get_decision(break_id)
        if decision and decision["decision"] == "REJECT":
            case["status"] = "REJECTED"
            _log(case, "CASE_REJECTED", f"by {decision['approver']}")
        else:
            case["status"] = "AWAITING_APPROVAL"
        return case

    if case["post_execution"] is None:
        break_row = investigation._tables()["breaks"][break_id]
        case["post_execution"] = execution_simulator.execute(break_id, case["investigation"], break_row)
        _log(case, "EXECUTION_COMPLETE")
        fire("post_execution", "Execution", "repair applied")

    break_row = investigation._tables()["breaks"][break_id]
    case["validation"] = validate(break_id, break_row, case["post_execution"])
    _log(case, "VALIDATION_COMPLETE", case["validation"]["reason"])
    fire("validation", "Validation Agent", case["validation"]["status"])

    case["status"] = case["validation"]["status"]  # CLOSED or REOPENED
    _log(case, f"CASE_{case['status']}")
    fire("done", "Orchestrator", f"case {case['status'].lower()} - sequencing complete")
    return case


def create_case(break_id, on_event=None):
    if break_id in _CASES:
        raise ValueError(f"case for {break_id} already exists - use resume_case() or get_case()")
    case = _new_case(break_id)
    _CASES[break_id] = case
    _log(case, "CASE_CREATED")
    return _advance(case, on_event=on_event)


def resume_case(break_id, on_event=None):
    """Call after control_gate.record_decision(break_id, ...) has been
    invoked externally by a human. Re-checks the gate and continues
    from wherever the case stopped."""
    case = _CASES.get(break_id)
    if case is None:
        raise KeyError(f"no case exists for {break_id} - call create_case() first")
    return _advance(case, on_event=on_event)


def get_case(break_id):
    return _CASES.get(break_id)


def reset():
    _CASES.clear()


if __name__ == "__main__":
    control_gate.reset()
    reset()
    breaks = investigation._tables()["breaks"]

    # PROPOSAL-tier: should flow straight through in one create_case() call.
    conf_id = next(bid for bid, b in breaks.items() if b["mismatch_type"] == "CONF_MISSING")
    print(f"=== PROPOSAL-tier case {conf_id} - single create_case() call ===")
    case = create_case(conf_id)
    print(f"  status after create_case: {case['status']}")

    # CONTROLLED_ACTION: should halt at AWAITING_APPROVAL, then resume after approval.
    ssi_id = next(bid for bid, b in breaks.items() if b["mismatch_type"] == "SETL_WRONG_SSI")
    print(f"\n=== CONTROLLED_ACTION case {ssi_id} - two-phase via create_case() + resume_case() ===")
    case = create_case(ssi_id)
    print(f"  status after create_case (before approval): {case['status']}")
    control_gate.record_decision(ssi_id, "APPROVE", "ops.head@resolvia.local", notes="verified SSI with custodian")
    case = resume_case(ssi_id)
    print(f"  status after resume_case (after approval): {case['status']}")

    print(f"\n  Full case history for {ssi_id}:")
    for e in case["history"]:
        print(f"    {e['timestamp']}  {e['event']:30s} {e['detail']}")

    # Full coverage through the Orchestrator's own interface (not the
    # agents directly) - confirms the wiring itself works, not just the
    # underlying agents in isolation.
    print(f"\n=== Coverage: create_case()+resume_case() through the Orchestrator, one break per root cause ===")
    control_gate.reset()
    reset()
    seen = set()
    outcomes = {}
    for bid, b in breaks.items():
        rc = b["mismatch_type"]
        if rc in seen:
            continue
        seen.add(rc)
        case = create_case(bid)
        if case["status"] == "AWAITING_APPROVAL":
            control_gate.record_decision(bid, "APPROVE", "coverage.run@resolvia.local")
            case = resume_case(bid)
        outcomes[rc] = case["status"]

    from collections import Counter
    print(f"  {len(seen)}/20 root causes: {dict(Counter(outcomes.values()))}")
