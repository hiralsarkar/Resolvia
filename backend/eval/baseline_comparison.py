"""
Compares Resolvia against the two ways a bank would do this without it.

Rules baseline: hand-written if/else rules over the same 15 features the
model sees, which is about what a rules engine or RPA bot could do without
reading documents. It gets the mechanical causes and misses the corporate
action ones, which look identical in the numbers.

Manual baseline: not a made-up stopwatch figure. It counts how many evidence
sources an analyst would have to open to reach a root cause: the four tables
every time, one more if the break has a document, and one more for the
corporate action notice.
"""

import os
import sys
from collections import Counter
import pandas as pd
from sklearn.metrics import f1_score

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "data"))
from features import build_features, DATA_DIR  # noqa: E402


def rules_predict(row):
    if row["cash_row_count"] == 0:
        return "CASH_MISSING_ENTRY"
    if row["cash_row_count"] == 2:
        return "CASH_DUPLICATE_ENTRY"
    if row["cash_currency_mismatch"]:
        return "CASH_FX_INPUT_DIFFERENCE"
    if abs(row["cash_amount_delta_pct"]) > 1e-9:
        return "CASH_WRONG_AMOUNT"
    if row["ssi_mismatch"]:
        return "SETL_WRONG_SSI"
    if row["instruction_missing"]:
        return "SETL_MISSING_INSTRUCTION"
    if row["settlement_pending"] and row["settlement_date_delta"] >= 2:
        return "SETL_LATE_COUNTERPARTY"
    if row["settlement_date_delta"] == 1 and not row["settlement_pending"] and not row["settlement_failed"]:
        return "SETL_INCORRECT_DATE"
    if row["confirmation_missing"]:
        return "CONF_MISSING"
    qty_off = abs(row["confirmed_qty_delta_pct"]) > 1e-9
    price_off = abs(row["price_delta_pct"]) > 1e-9
    if qty_off and price_off:
        return "CONF_DISAGREEMENT"
    if row["date_mismatch"] and not qty_off and not price_off and not row["counterparty_mismatch"]:
        return "TRADE_DATE_MISMATCH"
    if row["counterparty_mismatch"] and not qty_off and not price_off and not row["date_mismatch"]:
        return "TRADE_COUNTERPARTY_ID_MISMATCH"
    if price_off and not qty_off:
        return "TRADE_PRICE_MISMATCH"
    if qty_off and not price_off:
        return "TRADE_QUANTITY_MISMATCH"
    if row["qty_delta_pct"] <= -0.999:
        return "POS_MISSING_BOOKING"
    if abs(row["position_date_delta"]) > 0 and abs(row["qty_delta_pct"]) < 1e-9:
        return "POS_TIMING_DIFFERENCE"
    # Known clean CA ratios (1/1.5, 1/2, 1/3 and their "incorrect" cousins) -
    # a rules engine has no way to tell entitlement/mandatory/voluntary apart
    # without reading the corporate action notice, so it always guesses the
    # mechanical case. That's as far as rules can go here.
    ca_like = any(abs(row["qty_delta_pct"] - r) < 0.08 for r in (-1/3, -0.5, -2/3, -0.55, -0.45))
    if ca_like:
        return "CA_MANDATORY_NOT_REFLECTED"
    return "POS_WRONG_QUANTITY"


def manual_touches(needs_evidence, is_ca):
    touches = 4  # trades, positions, cash_transactions, settlements
    if needs_evidence:
        touches += 1
    if is_ca:
        touches += 1
    return touches


def main():
    df = build_features()
    breaks = pd.read_csv(os.path.join(DATA_DIR, "breaks.csv"))
    df = df.merge(breaks[["break_id", "needs_evidence_bundle", "corporate_action_type"]], on="break_id")

    test = df[df["split"] == "TEST"].copy()
    test["rules_pred"] = test.apply(rules_predict, axis=1)

    acc = (test["rules_pred"] == test["root_cause"]).mean()
    macro_f1 = f1_score(test["root_cause"], test["rules_pred"], average="macro", zero_division=0)
    print(f"Rules/RPA baseline on TEST ({len(test)} breaks): accuracy={acc:.3f} macro-F1={macro_f1:.3f}")
    print("(compare with docs/analysis/model_comparison.md, which ml_classifier/train.py writes, for the "
          "root_cause TEST macro-F1 across LogReg/RF/XGBoost)")

    wrong = test[test["rules_pred"] != test["root_cause"]]
    print(f"\nRules baseline misses ({len(wrong)}): by true root_cause -")
    for cause, n in Counter(wrong["root_cause"]).most_common(8):
        print(f"  {cause:30s} {n}")
    ca_causes = {"CA_INCORRECT_ENTITLEMENT", "CA_MANDATORY_NOT_REFLECTED", "CA_VOLUNTARY_DECISION"}
    ca_rows = test[test["root_cause"].isin(ca_causes)]
    ca_acc = (ca_rows["rules_pred"] == ca_rows["root_cause"]).mean() if len(ca_rows) else float("nan")
    print(f"\nRules accuracy on the 3 CA sub-causes specifically: {ca_acc:.3f} "
          f"(n={len(ca_rows)}). Expected to be low: this is where rules run out")

    df["manual_touches"] = df.apply(
        lambda r: manual_touches(bool(r["needs_evidence_bundle"]), r["corporate_action_type"] in ("MANDATORY", "VOLUNTARY")), axis=1)
    print(f"\nManual-style baseline (evidence-source touches, not fabricated time):")
    print(df.groupby("family")["manual_touches"].mean().round(2).to_string())
    print(f"Overall mean touches/break: {df['manual_touches'].mean():.2f}")


if __name__ == "__main__":
    main()
