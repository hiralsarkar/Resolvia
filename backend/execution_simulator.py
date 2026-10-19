"""
Execution simulator.

Applies the approved fix to a copy of the case's records so the Validation
agent has something to check. It never touches the source CSVs, and it is
only called after the Control Gate has said yes. It doesn't re-check the gate
itself; the gate is a separate piece of policy on purpose.

The fix applied is the one the proposal asked for, which comes from the RCA
diagnosis. If the diagnosis was wrong, the wrong fix gets applied and
Validation will catch it when it re-checks the break.

A few fixes depend on someone outside the bank (a counterparty settling, a
confirmation arriving). For those the repair stands for "that event has now
happened" rather than us forcing a value.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
from reference_data import EXPECTED_SSI, HOME_CURRENCY  # noqa: E402


def _book_position(case, trade, feed):
    case["position"]["actual_quantity"] = trade["quantity"]
    case["position"]["source"] = "CUSTODIAN"


def _fix_position_quantity(case, trade, feed):
    case["position"]["actual_quantity"] = trade["quantity"]


def _position_feed_catches_up(case, trade, feed):
    case["position"]["as_of_date"] = trade["settlement_date"]


def _apply_entitlement(case, trade, feed):
    # the entitled quantity is what the reconciliation expected to see
    case["position"]["actual_quantity"] = feed["source_value"]


def _hold(case, trade, feed):
    # voluntary event: nothing changes until the client's election arrives
    pass


def _post_cash(case, trade, feed):
    case["cash_transactions"] = [{
        "trade_id": trade["trade_id"], "account": f"ACC-{trade['portfolio']}",
        "currency": HOME_CURRENCY, "amount": trade["trade_value"], "expected_amount": trade["trade_value"],
        "value_date": trade["settlement_date"], "transaction_type": "SETTLEMENT", "status": "MATCHED",
    }]


def _reverse_duplicate(case, trade, feed):
    case["cash_transactions"] = case["cash_transactions"][:1]


def _fix_cash_amount(case, trade, feed):
    if case["cash_transactions"]:
        case["cash_transactions"][0]["amount"] = trade["trade_value"]


def _repost_cash_in_inr(case, trade, feed):
    if case["cash_transactions"]:
        case["cash_transactions"][0]["amount"] = trade["trade_value"]
        case["cash_transactions"][0]["currency"] = HOME_CURRENCY


def _resubmit_with_correct_ssi(case, trade, feed):
    s = case["settlement"]
    s["ssi_code"] = EXPECTED_SSI[trade["counterparty"]]
    s["instruction_status"] = "INSTRUCTED"
    s["settlement_status"] = "SETTLED"


def _counterparty_settles(case, trade, feed):
    case["settlement"]["settlement_date"] = trade["settlement_date"]
    case["settlement"]["settlement_status"] = "SETTLED"


def _send_instruction(case, trade, feed):
    s = case["settlement"]
    s["instruction_status"] = "INSTRUCTED"
    s["ssi_code"] = EXPECTED_SSI[trade["counterparty"]]
    s["settlement_status"] = "SETTLED"


def _fix_settlement_date(case, trade, feed):
    case["settlement"]["settlement_date"] = trade["settlement_date"]


def _agree_price(case, trade, feed):
    case["trade"]["confirmed_price"] = trade["price"]


def _agree_quantity(case, trade, feed):
    case["trade"]["confirmed_quantity"] = trade["quantity"]


def _agree_trade_date(case, trade, feed):
    case["trade"]["confirmed_trade_date"] = trade["trade_date"]


def _agree_counterparty(case, trade, feed):
    case["trade"]["confirmed_counterparty"] = trade["counterparty"]


def _confirmation_arrives(case, trade, feed):
    t = case["trade"]
    t["confirmation_status"] = "RECEIVED"
    t["confirmed_price"] = trade["price"]
    t["confirmed_quantity"] = trade["quantity"]
    t["confirmed_trade_date"] = trade["trade_date"]
    t["confirmed_counterparty"] = trade["counterparty"]


def _agree_terms(case, trade, feed):
    case["trade"]["confirmed_quantity"] = trade["quantity"]
    case["trade"]["confirmed_price"] = trade["price"]


REPAIRS = {
    "POS_MISSING_BOOKING": _book_position,
    "POS_WRONG_QUANTITY": _fix_position_quantity,
    "POS_TIMING_DIFFERENCE": _position_feed_catches_up,
    "CA_INCORRECT_ENTITLEMENT": _apply_entitlement,
    "CA_MANDATORY_NOT_REFLECTED": _apply_entitlement,
    "CA_VOLUNTARY_DECISION": _hold,
    "CASH_MISSING_ENTRY": _post_cash,
    "CASH_DUPLICATE_ENTRY": _reverse_duplicate,
    "CASH_WRONG_AMOUNT": _fix_cash_amount,
    "CASH_FX_INPUT_DIFFERENCE": _repost_cash_in_inr,
    "SETL_WRONG_SSI": _resubmit_with_correct_ssi,
    "SETL_LATE_COUNTERPARTY": _counterparty_settles,
    "SETL_MISSING_INSTRUCTION": _send_instruction,
    "SETL_INCORRECT_DATE": _fix_settlement_date,
    "TRADE_PRICE_MISMATCH": _agree_price,
    "TRADE_QUANTITY_MISMATCH": _agree_quantity,
    "TRADE_DATE_MISMATCH": _agree_trade_date,
    "TRADE_COUNTERPARTY_ID_MISMATCH": _agree_counterparty,
    "CONF_MISSING": _confirmation_arrives,
    "CONF_DISAGREEMENT": _agree_terms,
}


def execute(proposal, evidence, feed):
    """Applies proposal["root_cause"]'s fix to a deep copy of the records.

    The caller must already have an authorised gate check for this proposal."""
    case = copy.deepcopy(evidence["structured_evidence"])
    repair = REPAIRS.get(proposal["root_cause"])
    if repair is None:
        raise KeyError(f"no repair defined for {proposal['root_cause']}")
    repair(case, case["trade"], feed)
    case["applied_fix"] = proposal["root_cause"]
    return case
