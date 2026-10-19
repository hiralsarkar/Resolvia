"""
Resolution Proposal Agent: what should the bank do about it?

Proposal only. Every output is a proposal object that a person approves,
edits or rejects. The agent has no way of acting on its own suggestion.

It takes the RCA diagnosis as given and adds:

  action and expected outcome   looked up in ACTION_CATALOG. Once the cause is
                                known the fix is mechanical, so there is no
                                reason to have an LLM invent it each time.
  risk                          severity plus exposure (the trade value).
                                Plain arithmetic.
  authority tier                PROPOSAL for administrative steps (wait and
                                recheck, chase a counterparty, fix a date).
                                CONTROLLED_ACTION for anything that changes a
                                money amount, a quantity, an SSI or a
                                counterparty. Those always need a recorded
                                approval before anything runs.

Note the two flags at the end of a proposal. rca_flagged_for_human_review is
about the diagnosis (is it uncertain, is it a corporate action?).
approval_required is about the action (does it need sign-off?). A confident
diagnosis can still lead to an action that needs approval, so they stay
separate. The Control Gate looks at both.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from rca import analyze  # noqa: E402

HIGH_EXPOSURE_THRESHOLD = 1_000_000  # INR 10 lakh

PROPOSAL = "PROPOSAL"
CONTROLLED = "CONTROLLED_ACTION"

# root cause -> (action, expected outcome, authority tier, kind)
# kind: CORRECT changes records, FOLLOW_UP waits on someone outside the bank,
# HOLD changes nothing until the client decides.
ACTION_CATALOG = {
    "POS_MISSING_BOOKING": (
        "Book the missing transaction into the position system to reflect the trade.",
        "position quantity equals the booked trade quantity", CONTROLLED, "CORRECT"),
    "POS_WRONG_QUANTITY": (
        "Correct the recorded position quantity to match the booked trade quantity.",
        "position quantity equals the booked trade quantity", CONTROLLED, "CORRECT"),
    "POS_TIMING_DIFFERENCE": (
        "No correction needed - re-run reconciliation after the position feed catches up (expected to self-resolve within 1 business day).",
        "position as-of date lines up with the settlement date", PROPOSAL, "FOLLOW_UP"),
    "CA_INCORRECT_ENTITLEMENT": (
        "Recalculate and correct the entitlement quantity using the verified corporate action ratio.",
        "position reflects the correct post-event entitlement", CONTROLLED, "CORRECT"),
    "CA_MANDATORY_NOT_REFLECTED": (
        "Apply the mandatory corporate action ratio from the notice to the position.",
        "position quantity reflects the applied ratio", CONTROLLED, "CORRECT"),
    "CA_VOLUNTARY_DECISION": (
        "Hold. Don't change the position until the client or portfolio manager's election has been received and logged.",
        "no position change until an election instruction is on file", CONTROLLED, "HOLD"),
    "CASH_MISSING_ENTRY": (
        "Post the missing cash entry for the settled trade value.",
        "one cash entry exists for the trade value", CONTROLLED, "CORRECT"),
    "CASH_DUPLICATE_ENTRY": (
        "Reverse/cancel the duplicate cash entry, retaining only one posting.",
        "exactly one cash entry remains for the trade", CONTROLLED, "CORRECT"),
    "CASH_WRONG_AMOUNT": (
        "Correct the posted cash amount to match the expected trade value.",
        "posted amount equals the expected amount", CONTROLLED, "CORRECT"),
    "CASH_FX_INPUT_DIFFERENCE": (
        "Verify the FX rate/currency used and re-post the cash entry in the correct currency at the correct rate.",
        "currency and amount match the expected values", CONTROLLED, "CORRECT"),
    "SETL_WRONG_SSI": (
        "Correct the settlement instruction to the verified SSI for this counterparty and resubmit.",
        "SSI matches the verified one and the trade settles", CONTROLLED, "CORRECT"),
    "SETL_LATE_COUNTERPARTY": (
        "Escalate to the counterparty/custodian for a settlement status update; monitor for completion.",
        "trade shows as settled within the escalation SLA", PROPOSAL, "FOLLOW_UP"),
    "SETL_MISSING_INSTRUCTION": (
        "Issue the missing settlement instruction using the verified SSI/custodian details.",
        "instruction status becomes INSTRUCTED", CONTROLLED, "CORRECT"),
    "SETL_INCORRECT_DATE": (
        "Correct the recorded settlement date to match the actual settlement date.",
        "settlement date matches the confirmed date", PROPOSAL, "CORRECT"),
    "TRADE_PRICE_MISMATCH": (
        "Verify the correct trade price with the counterparty and amend the booking if confirmed.",
        "booked and confirmed prices agree", CONTROLLED, "CORRECT"),
    "TRADE_QUANTITY_MISMATCH": (
        "Verify the correct trade quantity with the counterparty and amend the booking if confirmed.",
        "booked and confirmed quantities agree", CONTROLLED, "CORRECT"),
    "TRADE_DATE_MISMATCH": (
        "Correct the trade date to match the confirmed date.",
        "booked and confirmed trade dates agree", PROPOSAL, "CORRECT"),
    "TRADE_COUNTERPARTY_ID_MISMATCH": (
        "Verify the correct counterparty with the confirming party and amend the booking if confirmed.",
        "booked and confirmed counterparty agree", CONTROLLED, "CORRECT"),
    "CONF_MISSING": (
        "Follow up with the counterparty/broker to obtain the outstanding trade confirmation.",
        "confirmation received and matched to the booking", PROPOSAL, "FOLLOW_UP"),
    "CONF_DISAGREEMENT": (
        "Reconcile the disagreement directly with the counterparty and amend the booking if their confirmation is correct.",
        "booking and confirmation agree", CONTROLLED, "CORRECT"),
}


def assess_risk(evidence):
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


def propose(break_id, rca_result=None, evidence=None):
    if evidence is None:
        from investigation import investigate
        evidence = investigate(break_id)
    if rca_result is None:
        rca_result = analyze(break_id, evidence=evidence)

    root_cause = rca_result["root_cause"]
    if root_cause not in ACTION_CATALOG:
        raise KeyError(f"no catalogue entry for root cause {root_cause}")
    action, outcome, tier, kind = ACTION_CATALOG[root_cause]
    needs_approval = tier == CONTROLLED or rca_result["requires_human_decision"]

    return {
        "break_id": break_id,
        "root_cause": root_cause,
        "rca_confidence": rca_result["confidence"],
        "recommended_action": action,
        "action_kind": kind,
        "reason": f"Diagnosed as {root_cause} (confidence {rca_result['confidence']:.2f}). "
                  f"Expected {rca_result['expected']!r}, observed {rca_result['actual']!r} "
                  f"on {rca_result['field']}.",
        "expected_outcome": outcome,
        "risk": assess_risk(evidence),
        "authority_tier": tier,
        "approval_required": needs_approval,
        "rca_flagged_for_human_review": rca_result["requires_human_decision"],
        "rca_escalation_reasons": rca_result["escalation_reasons"],
        "evidence_cited": rca_result["evidence_cited"],
        "status": "AWAITING_APPROVAL" if needs_approval else "AWAITING_REVIEW",
    }


if __name__ == "__main__":
    from investigation import _tables
    from collections import Counter

    tiers = Counter(tier for _, _, tier, _ in ACTION_CATALOG.values())
    print(f"{len(ACTION_CATALOG)} root causes in the catalogue: {dict(tiers)}")

    bid = next(iter(_tables()["breaks"]))
    p = propose(bid)
    print(f"\n{bid}: {p['root_cause']}")
    print(f"  {p['recommended_action']}")
    print(f"  risk {p['risk']['level']}, tier {p['authority_tier']}, approval required: {p['approval_required']}")
