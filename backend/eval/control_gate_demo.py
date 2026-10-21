"""
Shows the Control Gate doing its job, through the Orchestrator.

  1. A wrong-SSI payment break: blocked, then approved, executed, validated.
  2. A wrong cash amount: a person rejects it, nothing runs, the case stays open.
  3. A missing confirmation: administrative, so policy lets it through.
  4. One break per root cause, end to end.

Run from backend/:  python eval/control_gate_demo.py
"""

import os
import sys
from collections import Counter


# batch runs use a throwaway database, never the real audit trail
os.environ.setdefault("RESOLVIA_DB", ":memory:")
os.environ.setdefault("RESOLVIA_INVESTIGATOR", "off")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "agents"))

import control_gate as gate  # noqa: E402
import orchestrator  # noqa: E402
from investigation import _tables  # noqa: E402


def first_break(root_cause):
    return next(bid for bid, b in _tables()["breaks"].items() if b["mismatch_type"] == root_cause)


def show(case):
    print(f"  {case['break_id']}: {case['status']}  ({case['gate_result']['reason']})")


def main():
    gate.reset()
    orchestrator.reset()

    print("1. Wrong SSI, blocked then approved")
    bid = first_break("SETL_WRONG_SSI")
    show(orchestrator.create_case(bid))
    gate.record_decision(bid, "APPROVE", "ops.lead@resolvia.local", notes="SSI confirmed with custodian")
    show(orchestrator.resume_case(bid))
    for e in gate.audit_trail(bid):
        print(f"    {e['timestamp']}  {e['event']:24s} {e['detail']}")

    print("\n2. Wrong cash amount, rejected")
    bid = first_break("CASH_WRONG_AMOUNT")
    orchestrator.create_case(bid)
    gate.record_decision(bid, "REJECT", "ops.lead@resolvia.local", notes="need the broker statement first")
    case = orchestrator.resume_case(bid)
    show(case)
    print(f"    anything executed? {case['post_execution'] is not None}")

    print("\n3. Missing confirmation, administrative")
    show(orchestrator.create_case(first_break("CONF_MISSING")))

    print("\n4. Every root cause once")
    gate.reset()
    orchestrator.reset()
    seen, outcomes = set(), Counter()
    for bid, b in _tables()["breaks"].items():
        if b["mismatch_type"] in seen:
            continue
        seen.add(b["mismatch_type"])
        case = orchestrator.create_case(bid)
        if case["status"] == "AWAITING_APPROVAL":
            gate.record_decision(bid, "APPROVE", "coverage@resolvia.local")
            case = orchestrator.resume_case(bid)
        outcomes[case["status"]] += 1
    print(f"  {len(seen)} root causes: {dict(outcomes)}")


if __name__ == "__main__":
    main()
