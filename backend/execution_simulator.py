"""
Execution Simulator - "Controlled Execution Simulator" from the
architecture notes: simulates applying an approved
corrective action to the case's records. Only ever called AFTER
control_gate.check_gate() returns authorized=True - this module trusts
its caller on that, it does not re-check the gate itself (the gate is a
separate, independently-testable policy layer on purpose).

Operates on a deep COPY of the structured records, never the source
CSVs - this is a simulation for the Validation Agent to check, not a
real system-of-record mutation. Each repair function is the direct
inverse of the matching injector in data/generate_trade_breaks.py -
that symmetry is deliberate: the generator broke it, this fixes it,
Validation checks the fix landed.

A few root causes have no field to simply "set correct" because the
correction depends on an external party responding (chasing a missing
confirmation, waiting for a counterparty to settle, waiting for a
corporate-action election) - those repairs represent "the external
event has now happened," not "we forced a value," and are called out
as such in their function docstrings.
"""

import copy
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data"))
from generate_trade_breaks import EXPECTED_SSI  # noqa: E402


def _repair_pos_missing_booking(case, trade):
    case["position"]["actual_quantity"] = trade["quantity"]
    case["position"]["source"] = "CUSTODIAN"
    return case


def _repair_pos_wrong_quantity(case, trade):
    case["position"]["actual_quantity"] = trade["quantity"]
    return case


def _repair_pos_timing_difference(case, trade):
    """Self-resolves - the position feed catches up. Simulated as the
    as_of_date advancing to match settlement_date."""
    case["position"]["as_of_date"] = trade["settlement_date"]
    return case


def _repair_ca_incorrect_entitlement(case, trade, break_row):
    case["position"]["actual_quantity"] = break_row["source_value"]
    return case


def _repair_ca_mandatory_not_reflected(case, trade, break_row):
    case["position"]["actual_quantity"] = break_row["source_value"]
    return case


def _repair_ca_voluntary_decision(case, trade, break_row):
    """No repair is applied here - per ACTION_CATALOG this root cause's
    recommended action is HOLD. If this function is ever reached with
    authorization, that itself is a governance bug upstream (this
    should never get a CONTROLLED_ACTION approval to correct a
    quantity - only a logged election-received event would move it,
    which isn't modeled in this build). Returns the case unchanged."""
    return case


def _repair_cash_missing_entry(case, trade):
    case["cash_transactions"] = [{
        "trade_id": trade["trade_id"], "account": f"ACC-{trade['portfolio']}",
        "currency": "INR", "amount": trade["trade_value"], "expected_amount": trade["trade_value"],
        "value_date": trade["settlement_date"], "transaction_type": "SETTLEMENT", "status": "MATCHED",
    }]
    return case


def _repair_cash_duplicate_entry(case):
    if len(case["cash_transactions"]) > 1:
        case["cash_transactions"] = case["cash_transactions"][:1]
    return case


def _repair_cash_wrong_amount(case, trade):
    case["cash_transactions"][0]["amount"] = trade["trade_value"]
    return case


def _repair_cash_fx_input_difference(case, trade):
    case["cash_transactions"][0]["amount"] = trade["trade_value"]
    case["cash_transactions"][0]["currency"] = "INR"
    return case


def _repair_setl_wrong_ssi(case, break_row):
    case["settlement"]["ssi_code"] = break_row["source_value"]
    case["settlement"]["settlement_status"] = "SETTLED"
    case["settlement"]["instruction_status"] = "INSTRUCTED"
    return case


def _repair_setl_late_counterparty(case, trade):
    """External event: the counterparty has now settled. Not a value we
    can force - this represents that the escalation succeeded."""
    case["settlement"]["settlement_date"] = trade["settlement_date"]
    case["settlement"]["settlement_status"] = "SETTLED"
    return case


def _repair_setl_missing_instruction(case, trade):
    case["settlement"]["instruction_status"] = "INSTRUCTED"
    case["settlement"]["ssi_code"] = EXPECTED_SSI[trade["counterparty"]]
    case["settlement"]["settlement_status"] = "SETTLED"
    return case


def _repair_setl_incorrect_date(case, trade):
    case["settlement"]["settlement_date"] = trade["settlement_date"]
    return case


def _repair_trade_price_mismatch(case, break_row):
    case["trade"]["confirmed_price"] = break_row["source_value"]
    return case


def _repair_trade_quantity_mismatch(case, break_row):
    case["trade"]["confirmed_quantity"] = break_row["source_value"]
    return case


def _repair_trade_date_mismatch(case, break_row):
    case["trade"]["confirmed_trade_date"] = break_row["source_value"]
    return case


def _repair_trade_counterparty_id_mismatch(case, break_row):
    case["trade"]["confirmed_counterparty"] = break_row["source_value"]
    return case


def _repair_conf_missing(case, trade):
    """External event: the counterparty has now sent the confirmation,
    and it agrees with the booking."""
    case["trade"]["confirmation_status"] = "RECEIVED"
    case["trade"]["confirmed_quantity"] = trade["quantity"]
    case["trade"]["confirmed_price"] = trade["price"]
    return case


def _repair_conf_disagreement(case, trade):
    """External event: reconciled directly with the counterparty,
    agreed the booking was correct."""
    case["trade"]["confirmed_quantity"] = trade["quantity"]
    case["trade"]["confirmed_price"] = trade["price"]
    return case


def execute(break_id, evidence, break_row):
    """Simulates the approved corrective action. Caller MUST have
    already confirmed control_gate.check_gate(proposal)["authorized"]
    is True - this function does not check the gate itself."""
    structured = evidence["structured_evidence"]
    case = copy.deepcopy(structured)
    trade = case["trade"]
    root_cause = break_row["mismatch_type"]

    single_arg_case_trade = {
        "POS_MISSING_BOOKING": _repair_pos_missing_booking,
        "POS_WRONG_QUANTITY": _repair_pos_wrong_quantity,
        "POS_TIMING_DIFFERENCE": _repair_pos_timing_difference,
        "CASH_MISSING_ENTRY": _repair_cash_missing_entry,
        "CASH_WRONG_AMOUNT": _repair_cash_wrong_amount,
        "CASH_FX_INPUT_DIFFERENCE": _repair_cash_fx_input_difference,
        "SETL_LATE_COUNTERPARTY": _repair_setl_late_counterparty,
        "SETL_MISSING_INSTRUCTION": _repair_setl_missing_instruction,
        "SETL_INCORRECT_DATE": _repair_setl_incorrect_date,
        "CONF_MISSING": _repair_conf_missing,
        "CONF_DISAGREEMENT": _repair_conf_disagreement,
    }
    case_only = {"CASH_DUPLICATE_ENTRY": _repair_cash_duplicate_entry}
    case_trade_break = {
        "CA_INCORRECT_ENTITLEMENT": _repair_ca_incorrect_entitlement,
        "CA_MANDATORY_NOT_REFLECTED": _repair_ca_mandatory_not_reflected,
        "CA_VOLUNTARY_DECISION": _repair_ca_voluntary_decision,
    }
    case_break_only = {
        "SETL_WRONG_SSI": _repair_setl_wrong_ssi,
        "TRADE_PRICE_MISMATCH": _repair_trade_price_mismatch,
        "TRADE_QUANTITY_MISMATCH": _repair_trade_quantity_mismatch,
        "TRADE_DATE_MISMATCH": _repair_trade_date_mismatch,
        "TRADE_COUNTERPARTY_ID_MISMATCH": _repair_trade_counterparty_id_mismatch,
    }

    if root_cause in single_arg_case_trade:
        return single_arg_case_trade[root_cause](case, trade)
    if root_cause in case_only:
        return case_only[root_cause](case)
    if root_cause in case_trade_break:
        return case_trade_break[root_cause](case, trade, break_row)
    if root_cause in case_break_only:
        return case_break_only[root_cause](case, break_row)
    raise KeyError(f"no repair function for root cause {root_cause}")
