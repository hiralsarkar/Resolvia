"""
Feature engineering for the break classifiers.

For every break we join its trade, position, cash and settlement rows and
measure how far the outside world is from what we booked. Only those
observable differences go into the features. The label columns in
breaks.csv (break_type, mismatch_type) are carried along as targets and are
never used as inputs.
"""

import os

import pandas as pd

from reference_data import EXPECTED_SSI, HOME_CURRENCY

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

FEATURE_COLS = [
    "qty_delta_pct", "position_date_delta", "cash_row_count", "cash_amount_delta_pct",
    "cash_currency_mismatch", "settlement_date_delta", "ssi_mismatch", "instruction_missing",
    "settlement_failed", "settlement_pending", "price_delta_pct", "confirmed_qty_delta_pct",
    "date_mismatch", "counterparty_mismatch", "confirmation_missing",
]


def load(filename):
    return pd.read_csv(os.path.join(DATA_DIR, filename))


def _pct(new, old):
    if pd.isna(new) or not old:
        return 0.0
    return (new - old) / old


def _days(a, b):
    return (pd.to_datetime(a) - pd.to_datetime(b)).days


def build_features():
    trades = load("trades.csv").set_index("trade_id")
    positions = load("positions.csv").set_index("trade_id")
    settlements = load("settlements.csv").set_index("trade_id")
    cash = load("cash_transactions.csv")
    breaks = load("breaks.csv")

    cash_counts = cash.groupby("trade_id").size()
    cash_first = cash.groupby("trade_id").first()

    rows = []
    for _, b in breaks.iterrows():
        tid = b["source_record_id"]
        t, p, s = trades.loc[tid], positions.loc[tid], settlements.loc[tid]
        c = cash_first.loc[tid] if tid in cash_first.index else None

        has_cash = c is not None and pd.notna(c["expected_amount"]) and c["expected_amount"] != 0
        confirmed = t["confirmation_status"] == "RECEIVED"

        rows.append({
            "break_id": b["break_id"],
            "family": b["break_type"],
            "root_cause": b["mismatch_type"],
            "split": b["split"],

            "qty_delta_pct": _pct(p["actual_quantity"], p["expected_quantity"]),
            "position_date_delta": _days(p["as_of_date"], t["settlement_date"]),

            "cash_row_count": int(cash_counts.get(tid, 0)),
            "cash_amount_delta_pct": _pct(c["amount"], c["expected_amount"]) if has_cash else 0.0,
            "cash_currency_mismatch": int(c["currency"] != HOME_CURRENCY) if has_cash else 0,

            "settlement_date_delta": _days(s["settlement_date"], t["settlement_date"]),
            "ssi_mismatch": int(pd.notna(s["ssi_code"]) and s["ssi_code"] != EXPECTED_SSI.get(t["counterparty"])),
            "instruction_missing": int(s["instruction_status"] == "MISSING"),
            "settlement_failed": int(s["settlement_status"] == "FAILED"),
            "settlement_pending": int(s["settlement_status"] == "PENDING"),

            "price_delta_pct": _pct(t["confirmed_price"], t["price"]),
            "confirmed_qty_delta_pct": _pct(t["confirmed_quantity"], t["quantity"]),
            "date_mismatch": int(pd.notna(t["confirmed_trade_date"]) and t["confirmed_trade_date"] != t["trade_date"]),
            "counterparty_mismatch": int(pd.notna(t["confirmed_counterparty"])
                                         and t["confirmed_counterparty"] != t["counterparty"]),
            "confirmation_missing": int(not confirmed),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    df = build_features()
    print(f"{len(df)} breaks, {len(FEATURE_COLS)} features")
    print(df[FEATURE_COLS].describe().T[["mean", "min", "max"]])
