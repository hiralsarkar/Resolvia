"""
check_ml_targets.py

Empirical check for the choice of ML target: is the
4-class break-family target degenerate compared to the 20-class root-cause
target? Fits the same 3 candidate models (LogReg, RandomForest, XGBoost)
against both targets on the same engineered features and reports macro-F1
for each. This is a sanity check, not the real Week 2 model-comparison
deliverable (no tuning, no CV beyond a single stratified split) - its only
job is to decide which target Week 2 should build the real pipeline around.

Only breaking trades are used (root_cause is undefined for a clean trade).
"""

import csv
import os
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score
from xgboost import XGBClassifier

EXPECTED_SSI = {
    "ICICI-CUST": "SSI-IN-0091", "HDFC-CUST": "SSI-IN-0147",
    "KOTAK-CUST": "SSI-IN-0203", "DEUTSCHE-BROKER": "SSI-DE-5510",
    "MORGANSTANLEY-BROKER": "SSI-US-7742", "NOMURA-BROKER": "SSI-JP-3389",
}


DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def load(filename):
    # resolved against this script's own directory, not the caller's cwd -
    # this file is invoked both directly (cwd=data/) and via subprocess from
    # the EDA notebook (cwd=repo/data too, but don't rely on that matching)
    return pd.read_csv(os.path.join(DATA_DIR, filename))


def build_features():
    trades = load("trades.csv")
    positions = load("positions.csv")
    cash = load("cash_transactions.csv")
    settlements = load("settlements.csv")
    breaks = load("breaks.csv")

    trades = trades.set_index("trade_id")
    positions = positions.set_index("trade_id")
    settlements = settlements.set_index("trade_id")
    cash_counts = cash.groupby("trade_id").size().rename("cash_row_count")
    cash_first = cash.groupby("trade_id").first()

    rows = []
    for _, b in breaks.iterrows():
        tid = b["source_record_id"]
        t = trades.loc[tid]
        p = positions.loc[tid]
        s = settlements.loc[tid]
        n_cash = int(cash_counts.get(tid, 0))
        c = cash_first.loc[tid] if tid in cash_first.index else None

        expected_qty = p["expected_quantity"]
        qty_delta_pct = (p["actual_quantity"] - expected_qty) / expected_qty if expected_qty else 0
        position_date_delta = (pd.to_datetime(p["as_of_date"]) - pd.to_datetime(t["settlement_date"])).days

        if c is not None and pd.notna(c["expected_amount"]) and c["expected_amount"] != 0:
            cash_amount_delta_pct = (c["amount"] - c["expected_amount"]) / c["expected_amount"]
            cash_currency_mismatch = int(c["currency"] != "INR")
        else:
            cash_amount_delta_pct = 0.0
            cash_currency_mismatch = 0

        settlement_date_delta = (pd.to_datetime(s["settlement_date"]) - pd.to_datetime(t["settlement_date"])).days
        expected_ssi = EXPECTED_SSI.get(t["counterparty"])
        ssi_mismatch = int(pd.notna(s["ssi_code"]) and s["ssi_code"] != expected_ssi)
        instruction_missing = int(s["instruction_status"] == "MISSING")
        settlement_failed = int(s["settlement_status"] == "FAILED")
        settlement_pending = int(s["settlement_status"] == "PENDING")

        price_delta_pct = (t["confirmed_price"] - t["price"]) / t["price"] if pd.notna(t["confirmed_price"]) and t["price"] else 0
        confirmed_qty_delta_pct = (
            (t["confirmed_quantity"] - t["quantity"]) / t["quantity"]
            if pd.notna(t["confirmed_quantity"]) and t["quantity"] else 0
        )
        date_mismatch = int(t["confirmed_trade_date"] != t["trade_date"]) if pd.notna(t["confirmed_trade_date"]) else 0
        counterparty_mismatch = int(t["confirmed_counterparty"] != t["counterparty"]) if pd.notna(t["confirmed_counterparty"]) else 0
        confirmation_missing = int(t["confirmation_status"] != "RECEIVED")

        rows.append({
            "break_id": b["break_id"], "family": b["break_type"], "root_cause": b["mismatch_type"],
            "split": b["split"],
            "qty_delta_pct": qty_delta_pct, "position_date_delta": position_date_delta,
            "cash_row_count": n_cash, "cash_amount_delta_pct": cash_amount_delta_pct,
            "cash_currency_mismatch": cash_currency_mismatch,
            "settlement_date_delta": settlement_date_delta, "ssi_mismatch": ssi_mismatch,
            "instruction_missing": instruction_missing, "settlement_failed": settlement_failed,
            "settlement_pending": settlement_pending,
            "price_delta_pct": price_delta_pct, "confirmed_qty_delta_pct": confirmed_qty_delta_pct,
            "date_mismatch": date_mismatch, "counterparty_mismatch": counterparty_mismatch,
            "confirmation_missing": confirmation_missing,
        })
    return pd.DataFrame(rows)


FEATURE_COLS = [
    "qty_delta_pct", "position_date_delta", "cash_row_count", "cash_amount_delta_pct",
    "cash_currency_mismatch", "settlement_date_delta", "ssi_mismatch", "instruction_missing",
    "settlement_failed", "settlement_pending", "price_delta_pct", "confirmed_qty_delta_pct",
    "date_mismatch", "counterparty_mismatch", "confirmation_missing",
]

MODELS = {
    "LogisticRegression": lambda: LogisticRegression(max_iter=1000),
    "RandomForest": lambda: RandomForestClassifier(n_estimators=200, random_state=42),
    "XGBoost": lambda: XGBClassifier(n_estimators=200, random_state=42, eval_metric="mlogloss"),
}


def fit_and_report(df, target_col, label):
    X = df[FEATURE_COLS]
    y_raw = df[target_col]
    train_mask = df["split"] == "TRAIN"

    le = LabelEncoder()
    y = le.fit_transform(y_raw)

    X_train, X_test = X[train_mask], X[~train_mask]
    y_train, y_test = y[train_mask.values], y[~train_mask.values]

    print(f"\n=== Target: {label} ({df[target_col].nunique()} classes) "
          f"| train={len(X_train)} test={len(X_test)} ===")
    for name, ctor in MODELS.items():
        model = ctor()
        model.fit(X_train, y_train)
        preds = model.predict(X_test)
        macro_f1 = f1_score(y_test, preds, average="macro", zero_division=0)
        print(f"  {name:20s} macro-F1 = {macro_f1:.3f}")


if __name__ == "__main__":
    df = build_features()
    print(f"Built features for {len(df)} breaking trades.")
    fit_and_report(df, "family", "4-class break family (POSITION/CASH/SETTLEMENT/TRADE)")
    fit_and_report(df, "root_cause", "20-class root cause")
