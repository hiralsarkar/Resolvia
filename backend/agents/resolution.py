"""
Resolution Proposal Agent.

"What should the bank do?" Authority: Proposal only (per the proposal's
Agent Architecture table) - "It does NOT execute." Every output of this
agent is a PROPOSAL object for a human to approve, edit, or reject; the
agent has no path to act on its own recommendation.

Chains off the RCA Agent's output (root cause, confidence, alternatives,
escalation) - does not re-diagnose. Adds:
  - recommended_action / expected_outcome: deterministic, per root
    cause (ACTION_CATALOG below) - these are mechanical, well-defined
    corrective actions once the root cause is known, not something an
    LLM needs to invent each time.
  - risk: severity + a rough financial exposure figure (trade_value),
    the "Impact" piece is folded into this stage rather than a
    separate Impact Agent ("AI interprets, code
    calculates" - exposure is arithmetic, not reasoning).
  - authority_tier / approval_required: the three-tier model from the
    architecture discussion (Information / Proposal / Controlled
    Action). Every corrective action that changes a financial value,
    beneficiary/SSI, or counterparty is CONTROLLED_ACTION and always
    requires explicit human approval before any execution; purely
    administrative corrections (a date-only fix, "wait and recheck",
    "chase the counterparty") are PROPOSAL-tier - still reviewed, but
    not gated behind the heavier sign-off.

approval_required is INTENTIONALLY separate from RCA's
requires_human_decision - one is about whether the DIAGNOSIS needs
review (confidence/CA-status), the other is about whether the ACTION
needs authorization before it can be executed. A high-confidence,
non-CA diagnosis can still produce a CONTROLLED_ACTION proposal (e.g.
booking a large missing trade) - conflating the two flags would be a
governance bug, not a simplification.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rca import analyze  # noqa: E402

HIGH_EXPOSURE_THRESHOLD = 1_000_000  # INR, arbitrary but stated explicitly - not hidden in code

# (recommended_action, expected_outcome, authority_tier)
ACTION_CATALOG = {
    "POS_MISSING_BOOKING": (
        "Book the missing transaction into the position system to reflect the trade.",
        "position.actual_quantity equals position.expected_quantity", "CONTROLLED_ACTION"),
    "POS_WRONG_QUANTITY": (
        "Correct the recorded position quantity to match the booked trade quantity.",
        "position.actual_quantity equals position.expected_quantity", "CONTROLLED_ACTION"),
    "POS_TIMING_DIFFERENCE": (
        "No correction needed - re-run reconciliation after the position feed catches up "
        "(expected to self-resolve within 1 business day).",
        "position.as_of_date aligns with settlement_date on the next cycle", "PROPOSAL"),
    "CA_INCORRECT_ENTITLEMENT": (
        "Recalculate and correct the entitlement quantity using the verified corporate action ratio.",
        "position reflects the correct post-CA entitlement", "CONTROLLED_ACTION"),
    "CA_MANDATORY_NOT_REFLECTED": (
        "Apply the mandatory corporate action ratio to the position (mechanical correction, "
        "pending confirmation this is genuinely mandatory - see corporate_action_context).",
        "position.actual_quantity reflects the applied ratio", "CONTROLLED_ACTION"),
    "CA_VOLUNTARY_DECISION": (
        "HOLD - do not action. Await the client/portfolio manager's election instruction for "
        "this voluntary corporate action before any position change.",
        "no position change until an election instruction is received and logged", "CONTROLLED_ACTION"),
    "CASH_MISSING_ENTRY": (
        "Post the missing cash entry for the settled trade value.",
        "a cash_transactions row exists with amount equal to trade_value", "CONTROLLED_ACTION"),
    "CASH_DUPLICATE_ENTRY": (
        "Reverse/cancel the duplicate cash entry, retaining only one posting.",
        "exactly one cash_transactions row remains for the trade", "CONTROLLED_ACTION"),
    "CASH_WRONG_AMOUNT": (
        "Correct the posted cash amount to match the expected trade value.",
        "cash.amount equals cash.expected_amount", "CONTROLLED_ACTION"),
    "CASH_FX_INPUT_DIFFERENCE": (
        "Verify the FX rate/currency used and re-post the cash entry in the correct currency at "
        "the correct rate.",
        "cash.currency and cash.amount match the expected values", "CONTROLLED_ACTION"),
    "SETL_WRONG_SSI": (
        "Correct the settlement instruction to the verified SSI for this counterparty and resubmit.",
        "settlement.ssi_code matches the verified SSI; settlement_status progresses to SETTLED",
        "CONTROLLED_ACTION"),
    "SETL_LATE_COUNTERPARTY": (
        "Escalate to the counterparty/custodian for a settlement status update; monitor for completion.",
        "settlement_status becomes SETTLED within the escalation SLA", "PROPOSAL"),
    "SETL_MISSING_INSTRUCTION": (
        "Issue the missing settlement instruction using the verified SSI/custodian details.",
        "instruction_status becomes INSTRUCTED", "CONTROLLED_ACTION"),
    "SETL_INCORRECT_DATE": (
        "Correct the recorded settlement date to match the actual settlement date.",
        "settlement.settlement_date matches the confirmed date", "PROPOSAL"),
    "TRADE_PRICE_MISMATCH": (
        "Verify the correct trade price with the counterparty and amend the booking if confirmed.",
        "booked price matches the confirmed price", "CONTROLLED_ACTION"),
    "TRADE_QUANTITY_MISMATCH": (
        "Verify the correct trade quantity with the counterparty and amend the booking if confirmed.",
        "booked quantity matches the confirmed quantity", "CONTROLLED_ACTION"),
    "TRADE_DATE_MISMATCH": (
        "Correct the trade date to match the confirmed date.",
        "booked trade_date matches the confirmed date", "PROPOSAL"),
    "TRADE_COUNTERPARTY_ID_MISMATCH": (
        "Verify the correct counterparty with the confirming party and amend the booking if confirmed.",
        "booked counterparty matches the confirmed counterparty", "CONTROLLED_ACTION"),
    "CONF_MISSING": (
        "Follow up with the counterparty/broker to obtain the outstanding trade confirmation.",
        "confirmation received and matched against the booking", "PROPOSAL"),
    "CONF_DISAGREEMENT": (
        "Reconcile the disagreement directly with the counterparty and amend the booking if their "
        "confirmation is correct.",
        "booking matches the agreed/confirmed trade details", "CONTROLLED_ACTION"),
}


def assess_risk(rca_result, evidence):
    trade = evidence["structured_evidence"]["trade"]
    exposure = float(trade["trade_value"]) if trade and trade.get("trade_value") else 0.0
    severity = evidence["severity"]

    if severity == "P0" or exposure >= HIGH_EXPOSURE_THRESHOLD:
        level = "HIGH"
    elif severity == "P1":
        level = "MEDIUM"
    else:
        level = "LOW"

    return {"level": level, "financial_exposure": exposure, "severity": severity}


def propose(break_id, rca_result=None, evidence=None)
    """Resolution Proposal Agent entry point. Chains off RCA - re-uses
    its diagnosis rather than re-deriving it."""
    if rca_result is None:
        rca_result = analyze(break_id)
    if evidence is None:
        from investigation import investigate
        evidence = investigate(break_id)

    root_cause = rca_result["root_cause"]
    if root_cause not in ACTION_CATALOG:
        raise KeyError(f"no action catalog entry for root cause {root_cause}")
    action, expected_outcome, authority_tier = ACTION_CATALOG[root_cause]
    risk = assess_risk(rca_result, evidence)

    return {
        "break_id": break_id,
        "root_cause": root_cause,
        "rca_confidence": rca_result["confidence"],
        "recommended_action": action,
        "reason": f"Root cause identified as {root_cause} (confidence {rca_result['confidence']:.2f}). "
                  f"Expected {rca_result['expected']!r}, observed {rca_result['actual']!r} "
                  f"on {rca_result['field']}.",
        "expected_outcome": expected_outcome,
        "risk": risk,
        "authority_tier": authority_tier,
        "approval_required": authority_tier == "CONTROLLED_ACTION",
        "rca_flagged_for_human_review": rca_result["requires_human_decision"],
        "rca_escalation_reasons": rca_result["escalation_reasons"],
        "evidence_cited": rca_result["evidence_cited"],
        "status": "AWAITING_APPROVAL" if authority_tier == "CONTROLLED_ACTION" else "AWAITING_REVIEW",
    }


if __name__ == "__main__":
    from investigation import _tables
    breaks = _tables()["breaks"]

    seen_causes = set()
    sample_ids = []
    for bid, b in breaks.items():
        if b["mismatch_type"] not in seen_causes:
            seen_causes.add(b["mismatch_type"])
            sample_ids.append(bid)
        if len(sample_ids) >= 6:
            break

    controlled = proposal = 0
    for bid in sample_ids:
        p = propose(bid)
        print(f"\n=== {bid} ({p['root_cause']}) ===")
        print(f"  action: {p['recommended_action']}")
        print(f"  risk: {p['risk']['level']} (exposure {p['risk']['financial_exposure']:,.0f}, "
              f"severity {p['risk']['severity']})")
        print(f"  authority_tier={p['authority_tier']}  approval_required={p['approval_required']}  "
              f"status={p['status']}")
        if p["authority_tier"] == "CONTROLLED_ACTION":
            controlled += 1
        else:
            proposal += 1

    print(f"\n{controlled} CONTROLLED_ACTION / {proposal} PROPOSAL across "
          f"{len(sample_ids)} sampled root causes")
    print(f"\nFull ACTION_CATALOG covers {len(ACTION_CATALOG)} root causes "
          f"(taxonomy has {len(seen_causes) if len(sample_ids) >= 20 else 20})")
