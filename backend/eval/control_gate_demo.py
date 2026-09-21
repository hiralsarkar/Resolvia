"""
control_gate_demo.py

The flagship demo the architecture discussion called out repeatedly:
  Agent -> propose CONTROLLED_ACTION -> attempt execution -> BLOCKED
  (no human authorization) -> human APPROVEs -> attempt again ->
  AUTHORIZED -> execute -> validate -> CLOSE.
Plus a REJECT path (human rejects, case stays open, no execution ever
attempted) and a coverage run across all 20 root causes to confirm the
whole chain (propose -> gate -> execute -> validate) works end to end,
not just for the one hand-picked demo case.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agents"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from resolution import propose
from investigation import investigate, _tables
import control_gate as gate
import execution_simulator as sim
from validation import validate


def run_case(break_id, human_decision=None, approver="ops.review@resolvia.local"):
    proposal = propose(break_id)
    break_row = _tables()["breaks"][break_id]
    evidence = investigate(break_id)

    print(f"\n--- {break_id} ({proposal['root_cause']}, {proposal['authority_tier']}) ---")
    print(f"  proposed action: {proposal['recommended_action']}")

    check1 = gate.check_gate(proposal)
    print(f"  gate check (before any decision): authorized={check1['authorized']} - {check1['reason']}")

    if not check1["authorized"] and proposal["authority_tier"] == "CONTROLLED_ACTION":
        result_before = validate(break_id, break_row, None)
        print(f"  validation (nothing executed): {result_before['status']} - {result_before['reason']}")

    if human_decision:
        gate.record_decision(break_id, human_decision, approver,
                              notes="demo run" if human_decision == "APPROVE" else "insufficient evidence")
        check2 = gate.check_gate(proposal)
        print(f"  gate check (after {human_decision}): authorized={check2['authorized']} - {check2['reason']}")

        if check2["authorized"]:
            post_state = sim.execute(break_id, evidence, break_row)
            result = validate(break_id, break_row, post_state)
        else:
            result = validate(break_id, break_row, None)
        print(f"  final status: {result['status']} - {result['reason']}")
        return result["status"]

    return None


def main():
    gate.reset()
    breaks = _tables()["breaks"]

    # 1. The flagship demo: a CONTROLLED_ACTION break, blocked then approved.
    ssi_break = next(bid for bid, b in breaks.items() if b["mismatch_type"] == "SETL_WRONG_SSI")
    print("=== DEMO 1: CONTROLLED_ACTION, blocked then approved (the payment-safety flagship case) ===")
    run_case(ssi_break, human_decision="APPROVE")
    print(f"\n  Audit trail for {ssi_break}:")
    for e in gate.audit_trail(ssi_break):
        print(f"    {e['timestamp']}  {e['event']:25s} {e['detail']}")

    # 2. A CONTROLLED_ACTION break that gets REJECTED - stays open, nothing executes.
    cash_break = next(bid for bid, b in breaks.items() if b["mismatch_type"] == "CASH_WRONG_AMOUNT")
    print("\n=== DEMO 2: CONTROLLED_ACTION, REJECTED by a human ===")
    run_case(cash_break, human_decision="REJECT")

    # 3. A PROPOSAL-tier break - authorized by policy, no human decision needed.
    conf_break = next(bid for bid, b in breaks.items() if b["mismatch_type"] == "CONF_MISSING")
    print("\n=== DEMO 3: PROPOSAL tier, no human decision recorded at all ===")
    proposal = propose(conf_break)
    break_row = breaks[conf_break]
    evidence = investigate(conf_break)
    check = gate.check_gate(proposal)
    print(f"  gate check: authorized={check['authorized']} - {check['reason']}")
    post_state = sim.execute(conf_break, evidence, break_row)
    result = validate(conf_break, break_row, post_state)
    print(f"  final status: {result['status']} - {result['reason']}")

    # 4. Full coverage: propose+gate+execute+validate for one break per root cause.
    print("\n=== COVERAGE: propose -> gate -> execute -> validate for all 20 root causes ===")
    gate.reset()
    seen = set()
    closed, reopened, blocked = 0, 0, 0
    for bid, b in breaks.items():
        rc = b["mismatch_type"]
        if rc in seen:
            continue
        seen.add(rc)
        proposal = propose(bid)
        if proposal["authority_tier"] == "CONTROLLED_ACTION":
            gate.record_decision(bid, "APPROVE", "coverage.run@resolvia.local")
        check = gate.check_gate(proposal)
        if not check["authorized"]:
            blocked += 1
            continue
        evidence = investigate(bid)
        post_state = sim.execute(bid, evidence, b)
        result = validate(bid, b, post_state)
        if result["status"] == "CLOSED":
            closed += 1
        elif result["status"] == "REOPENED":
            reopened += 1
            if rc == "CA_VOLUNTARY_DECISION":
                print(f"  EXPECTED REOPEN (by design): {bid} ({rc}) - a generic APPROVE never "
                      f"resolves this; only a logged election-received event should, and that's "
                      f"not modeled here - see execution_simulator's docstring on this function")
            else:
                print(f"  UNEXPECTED REOPEN: {bid} ({rc}) - {result['reason']}")

    print(f"\n{len(seen)}/20 root causes exercised: {closed} closed, {reopened} reopened, {blocked} blocked")


if __name__ == "__main__":
    main()
