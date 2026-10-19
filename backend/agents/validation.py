"""
Validation Agent: did the action actually clear the break?

It decides CLOSED or REOPENED, but only by checking records after the fact.
It doesn't authorise anything.

The check is the reconciliation itself, run again. The break feed says which
field disagreed and what value it should have had. After the fix we read that
field from the updated records and compare. It does not matter what we
thought the root cause was: if the diagnosis was wrong and the wrong fix was
applied, the field still won't match and the case is reopened.

Two outcomes are kept apart from a failed fix:
  OPEN     nothing ran because the gate blocked it. That's the gate working.
  ON_HOLD  the proposal was a deliberate hold (a voluntary corporate action
           waiting on the client's election). Nothing was meant to change.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data"))
from reference_data import HOME_CURRENCY  # noqa: E402


def _num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _same_number(a, b):
    x, y = _num(a), _num(b)
    return x is not None and y is not None and abs(x - y) < 0.005


def _one_cash_row_for(case, amount, currency=None):
    rows = case["cash_transactions"]
    if len(rows) != 1 or not _same_number(rows[0]["amount"], amount):
        return False
    return currency is None or rows[0]["currency"] == currency


def _parse_terms(text):
    # "qty=500,price=4137.77" -> {"qty": "500", "price": "4137.77"}
    return dict(part.split("=", 1) for part in str(text).split(",") if "=" in part)


def recheck(case, feed):
    """Re-runs the comparison that raised the break. Returns (cleared, what was compared)."""
    field, expected = feed["breaking_fields"], feed["source_value"]
    pos, setl, trade = case["position"], case["settlement"], case["trade"]

    checks = {
        "actual_quantity": lambda: (_same_number(pos["actual_quantity"], expected), pos["actual_quantity"]),
        "as_of_date": lambda: (pos["as_of_date"] == expected, pos["as_of_date"]),
        "amount": lambda: (_one_cash_row_for(case, expected), len(case["cash_transactions"])),
        "amount,cash_id": lambda: (_one_cash_row_for(case, expected), len(case["cash_transactions"])),
        "amount,currency": lambda: (_one_cash_row_for(case, expected, HOME_CURRENCY),
                                    [c["currency"] for c in case["cash_transactions"]]),
        "ssi_code": lambda: (setl["ssi_code"] == expected, setl["ssi_code"]),
        "settlement_date,settlement_status": lambda: (
            setl["settlement_date"] == expected and setl["settlement_status"] == "SETTLED",
            f"{setl['settlement_date']} {setl['settlement_status']}"),
        "instruction_status": lambda: (setl["instruction_status"] == expected, setl["instruction_status"]),
        "settlement_date": lambda: (setl["settlement_date"] == expected, setl["settlement_date"]),
        "price": lambda: (_same_number(trade["confirmed_price"], expected), trade["confirmed_price"]),
        "quantity": lambda: (_same_number(trade["confirmed_quantity"], expected), trade["confirmed_quantity"]),
        "trade_date": lambda: (trade["confirmed_trade_date"] == expected, trade["confirmed_trade_date"]),
        "counterparty": lambda: (trade["confirmed_counterparty"] == expected, trade["confirmed_counterparty"]),
        "confirmation": lambda: (trade["confirmation_status"] == "RECEIVED", trade["confirmation_status"]),
        "quantity,price": lambda: (
            _same_number(trade["confirmed_quantity"], _parse_terms(expected).get("qty"))
            and _same_number(trade["confirmed_price"], _parse_terms(expected).get("price")),
            f"qty={trade['confirmed_quantity']},price={trade['confirmed_price']}"),
    }
    if field not in checks:
        raise KeyError(f"don't know how to re-check field {field!r}")
    cleared, now = checks[field]()
    return cleared, now


def validate(break_id, feed, post_execution_case, proposal=None):
    if post_execution_case is None:
        return {"break_id": break_id, "status": "OPEN",
                "reason": "nothing was executed (blocked or not yet approved), so there is nothing to check"}

    if proposal is not None and proposal.get("action_kind") == "HOLD":
        return {"break_id": break_id, "status": "ON_HOLD",
                "reason": "position held as instructed; waiting for the client's election before any change"}

    cleared, now = recheck(post_execution_case, feed)
    if cleared:
        reason = f"{feed['breaking_fields']} now matches the expected {feed['source_value']}"
    else:
        reason = (f"{feed['breaking_fields']} still doesn't match: expected {feed['source_value']}, "
                  f"found {now}. Needs another look, not a retry")
    return {"break_id": break_id, "status": "CLOSED" if cleared else "REOPENED", "reason": reason}
