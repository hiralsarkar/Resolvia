"""
Validation Agent.

"Did the approved action actually resolve the break?" Authority: "No
unilateral material closure" per the proposal's Agent Architecture
table - this agent decides CLOSE or REOPEN, but it is checking a
post-execution state, not authorizing anything itself.

Compares the case state AFTER execution_simulator.execute() against
what the break's own source_value says the field should be - one
checker function per root cause, mirroring execution_simulator's
repair functions 1:1 (same dispatch pattern, deliberately - break ->
repair -> check should be traceable as three parallel, independently
readable steps, not one opaque generic diff).

If control_gate blocked execution (no authorization), there is no
post-execution state to check at all - the case simply stays open.
That's not a validation failure, it's the control gate working as
designed; the two must not be conflated in the output.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def _check_pos_missing_booking(case, trade, break_row):
    return case["position"]["actual_quantity"] == trade["quantity"]


def _check_pos_wrong_quantity(case, trade, break_row):
    return case["position"]["actual_quantity"] == trade["quantity"]


def _check_pos_timing_difference(case, trade, break_row):
    return case["position"]["as_of_date"] == trade["settlement_date"]


def _check_ca_incorrect_entitlement(case, trade, break_row):
    return str(case["position"]["actual_quantity"]) == str(break_row["source_value"])


def _check_ca_mandatory_not_reflected(case, trade, break_row):
    return str(case["position"]["actual_quantity"]) == str(break_row["source_value"])


def _check_ca_voluntary_decision(case, trade, break_row):
    """Should never validate as CLOSE via this path - ACTION_CATALOG's
    recommendation is HOLD, so execution_simulator's repair for this
    root cause is a deliberate no-op. If this checker ever runs against
    an actually-changed position, something upstream let a voluntary CA
    execute without an election - that's a governance failure to
    surface loudly, not a routine REOPEN."""
    return False


def _check_cash_missing_entry(case, trade, break_row):
    return len(case["cash_transactions"]) == 1 and \
        str(case["cash_transactions"][0]["amount"]) == str(trade["trade_value"])


def _check_cash_duplicate_entry(case, trade, break_row):
    return len(case["cash_transactions"]) == 1


def _check_cash_wrong_amount(case, trade, break_row):
    return str(case["cash_transactions"][0]["amount"]) == str(trade["trade_value"])


def _check_cash_fx_input_difference(case, trade, break_row):
    c = case["cash_transactions"][0]
    return str(c["amount"]) == str(trade["trade_value"]) and c["currency"] == "INR"


def _check_setl_wrong_ssi(case, trade, break_row):
    return case["settlement"]["ssi_code"] == break_row["source_value"]


def _check_setl_late_counterparty(case, trade, break_row):
    return case["settlement"]["settlement_status"] == "SETTLED"


def _check_setl_missing_instruction(case, trade, break_row):
    return case["settlement"]["instruction_status"] == "INSTRUCTED"


def _check_setl_incorrect_date(case, trade, break_row):
    return case["settlement"]["settlement_date"] == trade["settlement_date"]


def _check_trade_price_mismatch(case, trade, break_row):
    return str(case["trade"]["confirmed_price"]) == str(break_row["source_value"])


def _check_trade_quantity_mismatch(case, trade, break_row):
    return str(case["trade"]["confirmed_quantity"]) == str(break_row["source_value"])


def _check_trade_date_mismatch(case, trade, break_row):
    return case["trade"]["confirmed_trade_date"] == break_row["source_value"]


def _check_trade_counterparty_id_mismatch(case, trade, break_row):
    return case["trade"]["confirmed_counterparty"] == break_row["source_value"]


def _check_conf_missing(case, trade, break_row):
    return case["trade"]["confirmation_status"] == "RECEIVED"


def _check_conf_disagreement(case, trade, break_row):
    return str(case["trade"]["confirmed_quantity"]) == str(trade["quantity"]) and \
        str(case["trade"]["confirmed_price"]) == str(trade["price"])


CHECKERS = {
    "POS_MISSING_BOOKING": _check_pos_missing_booking,
    "POS_WRONG_QUANTITY": _check_pos_wrong_quantity,
    "POS_TIMING_DIFFERENCE": _check_pos_timing_difference,
    "CA_INCORRECT_ENTITLEMENT": _check_ca_incorrect_entitlement,
    "CA_MANDATORY_NOT_REFLECTED": _check_ca_mandatory_not_reflected,
    "CA_VOLUNTARY_DECISION": _check_ca_voluntary_decision,
    "CASH_MISSING_ENTRY": _check_cash_missing_entry,
    "CASH_DUPLICATE_ENTRY": _check_cash_duplicate_entry,
    "CASH_WRONG_AMOUNT": _check_cash_wrong_amount,
    "CASH_FX_INPUT_DIFFERENCE": _check_cash_fx_input_difference,
    "SETL_WRONG_SSI": _check_setl_wrong_ssi,
    "SETL_LATE_COUNTERPARTY": _check_setl_late_counterparty,
    "SETL_MISSING_INSTRUCTION": _check_setl_missing_instruction,
    "SETL_INCORRECT_DATE": _check_setl_incorrect_date,
    "TRADE_PRICE_MISMATCH": _check_trade_price_mismatch,
    "TRADE_QUANTITY_MISMATCH": _check_trade_quantity_mismatch,
    "TRADE_DATE_MISMATCH": _check_trade_date_mismatch,
    "TRADE_COUNTERPARTY_ID_MISMATCH": _check_trade_counterparty_id_mismatch,
    "CONF_MISSING": _check_conf_missing,
    "CONF_DISAGREEMENT": _check_conf_disagreement,
}


def validate(break_id, break_row, post_execution_case):
    """post_execution_case=None means the control gate blocked
    execution - the case stays open, and this is reported distinctly
    from a genuine post-execution mismatch."""
    if post_execution_case is None:
        return {"break_id": break_id, "status": "OPEN",
                "reason": "no action was executed (blocked or not yet authorized) - nothing to validate"}

    root_cause = break_row["mismatch_type"]
    checker = CHECKERS.get(root_cause)
    if checker is None:
        raise KeyError(f"no validation checker for root cause {root_cause}")

    trade = post_execution_case["trade"]
    resolved = checker(post_execution_case, trade, break_row)

    return {
        "break_id": break_id,
        "status": "CLOSED" if resolved else "REOPENED",
        "reason": "post-execution state matches expected outcome" if resolved
                  else "post-execution state still does not match expected outcome - "
                       "needs re-investigation, not another blind retry",
    }
