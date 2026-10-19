"""
Orchestrator.

It runs the workflow; it doesn't make financial decisions. The states:

  CASE_CREATED -> TRIAGE -> INVESTIGATION -> RCA -> RESOLUTION PROPOSAL
  -> CONTROL GATE -> (blocked: wait for a person) -> EXECUTION -> VALIDATION
  -> CLOSED / REOPENED / ON_HOLD

Cases are saved to SQLite (store.py) after every run, so an open case and
its history survive a restart.

It works in two phases because a program can't sit and wait for a person.
create_case() runs every automatic stage and stops at the first thing it
can't get past on its own: bad data, or an action that needs approval. The
case then waits in AWAITING_APPROVAL until someone calls
control_gate.record_decision(). resume_case() picks up from exactly where it
stopped.

The one decision the Orchestrator owns is what to do with the gate's answer:
stop, or carry on. It can't decide that approval isn't needed.

Every case keeps its own history of what happened and when. That's separate
from the gate's log and covers the whole pipeline.
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
import store  # noqa: E402
from validation import validate  # noqa: E402

_CASES = {}  # in-memory cache; store.py is the record


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
    """Runs every stage that hasn't run yet and stops at the first blocker.

    Safe to call again: each stage runs once. on_event(stage, label, detail)
    is an optional hook the UI uses to show progress as each stage really
    finishes. It never changes the flow."""
    break_id = case["break_id"]

    def fire(stage, label, detail):
        if on_event:
            on_event(stage, label, detail)

    if case["triage"] is None:
        t = case["triage"] = triage.triage(break_id)
        _log(case, "TRIAGE_COMPLETE", f"family={t['predicted_family']} priority={t['priority']} route={t['route']}")
        fire("triage", "Triage Agent", f"routed to {t['route']}, priority {t['priority']}")
        if not t["valid"]:
            case["status"] = "HALTED_DATA_QUALITY"
            _log(case, "CASE_HALTED", "; ".join(t["validation_issues"]))
            return case

    if case["investigation"] is None:
        case["investigation"] = investigation.investigate(break_id)
        has_doc = case["investigation"]["document_evidence"].get("has_document", False)
        _log(case, "INVESTIGATION_COMPLETE", f"has_document={has_doc}")
        fire("investigation", "Investigation Agent", "evidence gathered" + (", document read" if has_doc else ""))

    if case["rca"] is None:
        r = case["rca"] = rca.analyze(break_id, evidence=case["investigation"])
        _log(case, "RCA_COMPLETE", f"root_cause={r['root_cause']} confidence={r['confidence']:.2f} "
                                   f"requires_human_decision={r['requires_human_decision']}")
        if r.get("document_finding") and r["document_finding"]["changed"]:
            _log(case, "RCA_DOCUMENT_OVERRIDE",
                 f"model said {r['document_finding']['model_said']}, notice says "
                 f"{r['document_finding']['mandatory_flag']}")
        fire("rca", "RCA Agent", f"{r['root_cause']} at {r['confidence'] * 100:.1f}% confidence")

    if case["proposal"] is None:
        p = case["proposal"] = resolution.propose(break_id, rca_result=case["rca"], evidence=case["investigation"])
        _log(case, "RESOLUTION_PROPOSAL_COMPLETE",
             f"action={p['recommended_action'][:70]!r} authority_tier={p['authority_tier']} "
             f"approval_required={p['approval_required']}")
        fire("proposal", "Resolution Proposal Agent", p["authority_tier"].replace("_", " "))

    gate = case["gate_result"] = control_gate.check_gate(case["proposal"])
    _log(case, "GATE_CHECK:" + ("AUTHORIZED" if gate["authorized"] else "BLOCKED"), gate["reason"])
    fire("gate", "Orchestrator", "gate authorised, continuing" if gate["authorized"]
         else "gate blocked, waiting for a person")

    if not gate["authorized"]:
        decision = control_gate.get_decision(break_id)
        if decision and decision["decision"] == "REJECT":
            case["status"] = "REJECTED"
            _log(case, "CASE_REJECTED", f"by {decision['approver']}")
        else:
            case["status"] = "AWAITING_APPROVAL"
        return case

    feed = investigation.break_feed(break_id)
    if case["post_execution"] is None:
        case["post_execution"] = execution_simulator.execute(case["proposal"], case["investigation"], feed)
        _log(case, "EXECUTION_COMPLETE", f"applied fix for {case['proposal']['root_cause']}")
        fire("post_execution", "Execution", "fix applied")

    case["validation"] = validate(break_id, feed, case["post_execution"], case["proposal"])
    _log(case, "VALIDATION_COMPLETE", case["validation"]["reason"])
    fire("validation", "Validation Agent", case["validation"]["status"])

    case["status"] = case["validation"]["status"]
    _log(case, f"CASE_{case['status']}")
    fire("done", "Orchestrator", f"case {case['status'].lower().replace('_', ' ')}")
    return case


def save(case):
    """Writes the case to the database. The pipeline saves after every run;
    anything else that changes a case (the app's manual workflow) calls this."""
    store.save_case(case)
    return case


def create_case(break_id, on_event=None):
    if get_case(break_id) is not None:
        raise ValueError(f"a case for {break_id} already exists, use resume_case() or get_case()")
    case = _CASES[break_id] = _new_case(break_id)
    _log(case, "CASE_CREATED")
    return save(_advance(case, on_event=on_event))


def resume_case(break_id, on_event=None):
    """Call after control_gate.record_decision(). Re-checks the gate and carries on."""
    case = get_case(break_id)
    if case is None:
        raise KeyError(f"no case for {break_id}, call create_case() first")
    return save(_advance(case, on_event=on_event))


def get_case(break_id):
    if break_id not in _CASES:
        stored = store.load_case(break_id)
        if stored is None:
            return None
        _CASES[break_id] = stored
    return _CASES[break_id]


def case_statuses():
    return store.case_statuses()


def reset():
    _CASES.clear()
    store.reset("cases")


if __name__ == "__main__":
    os.environ.setdefault("RESOLVIA_DB", ":memory:")
    control_gate.reset()
    reset()
    breaks = investigation._tables()["breaks"]

    ssi = next(b for b, r in breaks.items() if r["mismatch_type"] == "SETL_WRONG_SSI")
    case = create_case(ssi)
    print(f"{ssi} after create_case: {case['status']}")
    control_gate.record_decision(ssi, "APPROVE", "ops.head@resolvia.local", notes="SSI checked with custodian")
    case = resume_case(ssi)
    print(f"{ssi} after approval: {case['status']}\n")
    for e in case["history"]:
        print(f"  {e['timestamp']}  {e['event']:30s} {e['detail']}")
