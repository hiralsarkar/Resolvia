"""
Shared helpers for the offline evaluations.

They replay what the live pipeline would do with a diagnosis, without opening
cases: who would have to look at it, and what Validation would say after the
fix runs. Training (to pick the confidence threshold), the stress tests and
the approval-policy simulation all use the same rules, which are the ones in
resolution.py, rca.py, execution_simulator.py and validation.py.
"""

import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
for p in (os.path.join(HERE, ".."), os.path.join(HERE, "..", "agents"),
          os.path.join(HERE, "..", "..", "data")):
    if p not in sys.path:
        sys.path.insert(0, p)

from resolution import ACTION_CATALOG  # noqa: E402
import execution_simulator  # noqa: E402
from validation import recheck  # noqa: E402

# what a person's time and a mistake cost, in "one review" units
COST_REVIEW = 1
COST_REOPEN = 5
COST_SILENT_ERROR = 50


def _clean(value):
    if isinstance(value, (np.floating, float)) and np.isnan(value):
        return None
    if isinstance(value, np.generic):
        return value.item()
    return value


def records_by_trade(frames):
    """trade_id -> the four records the execution simulator works on."""
    def rows(df):
        return [{k: _clean(v) for k, v in r.items()} for r in df.to_dict("records")]
    out = {}
    for t in rows(frames["trades"]):
        out[t["trade_id"]] = {"trade": t, "position": None, "cash_transactions": [], "settlement": None}
    for p in rows(frames["positions"]):
        out[p["trade_id"]]["position"] = p
    for s in rows(frames["settlements"]):
        out[s["trade_id"]]["settlement"] = s
    for c in rows(frames["cash_transactions"]):
        out[c["trade_id"]]["cash_transactions"].append(c)
    return out


def feed_of(break_row):
    """The break as the reconciliation engine would report it."""
    return {k: ("" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v))
            for k, v in break_row.items() if k not in ("mismatch_type", "root_cause", "second_cause")}


def outcome(predicted_cause, feed, records):
    """CLOSED, REOPENED or ON_HOLD after running the fix for predicted_cause."""
    kind = ACTION_CATALOG[predicted_cause][3]
    if kind == "HOLD":
        return "ON_HOLD"
    case = execution_simulator.execute({"root_cause": predicted_cause},
                                       {"structured_evidence": records}, feed)
    cleared, _ = recheck(case, feed)
    return "CLOSED" if cleared else "REOPENED"


def needs_person(predicted_cause, confidence, is_ca, threshold):
    tier = ACTION_CATALOG[predicted_cause][2]
    return tier == "CONTROLLED_ACTION" or is_ca or confidence < threshold


def routing_cost(rows, threshold):
    """rows: dicts with pred, conf, correct, is_ca, outcome_if_run.
    A person catches a wrong diagnosis they review; an unreviewed one runs."""
    reviews = reopens = silent = 0
    for r in rows:
        if needs_person(r["pred"], r["conf"], r["is_ca"], threshold):
            reviews += 1
            continue
        if r["outcome_if_run"] == "REOPENED":
            reopens += 1
        elif not r["correct"]:
            silent += 1
    cost = COST_REVIEW * reviews + COST_REOPEN * reopens + COST_SILENT_ERROR * silent
    return {"threshold": threshold, "reviews": reviews, "reopens": reopens,
            "silent_errors": silent, "cost": cost}


def as_frame(rows):
    return pd.DataFrame(rows)
