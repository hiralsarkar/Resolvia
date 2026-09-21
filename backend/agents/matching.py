"""
Matching Agent - Tier 1 (exact) and Tier 2 (tolerance) reconciliation.

From-scratch, deterministic - no model involved: a threshold check
doesn't need one.

For each trade pair_id, groups the internal-book and custodian-confirm
row(s) and decides:
  - MATCHED_TIER1  : exact match on symbol/quantity/price/counterparty/
                      settlement_date
  - MATCHED_TIER2  : not exact, but within tolerance (price within
                      PRICE_TOLERANCE_PCT, settlement date within
                      DATE_TOLERANCE_DAYS)
  - UNMATCHED      : anything else - missing side, duplicate side
                      (not exactly one row per side), or a genuine
                      mismatch outside tolerance. Escalates to Tier 2.5
                      (the ML Classifier) / the LLM tier.

A pair with anything other than exactly one INTERNAL_BOOK row and one
CUSTODIAN_CONFIRM row is deliberately never compared field-by-field -
the row-count mismatch itself (0 or 2+ on either side) is already the
signal (missing-on-one-side, duplicate booking), so it's classified
UNMATCHED immediately rather than forced through a two-row comparison
that doesn't apply.
"""

import csv
from collections import defaultdict
from datetime import datetime

PRICE_TOLERANCE_PCT = 0.5   # price within 0.5% counts as Tier 2

# NOTE: kept at 0, not 1. The synthetic generator's SETTLEMENT_DATE_MISMATCH
# break type injects an exactly-1-day shift (holiday-calendar-style), so a
# 1-day tolerance here would silently absorb every instance of that labeled
# break as "matched" - confirmed empirically via backend/eval/baseline_
# matching_eval.py (100% of that category was missed with tolerance=1). Any
# date difference is left flagged as unmatched; deciding whether it's a
# benign known-holiday difference is the Classification Agent's job later,
# per review-doc category #6, not something Tier 2 should silently swallow.
DATE_TOLERANCE_DAYS = 0

FIELDS_TO_COMPARE = ["symbol", "quantity", "price", "counterparty", "settlement_date"]


def _parse_date(d):
    return datetime.strptime(d, "%Y-%m-%d")


def load_pairs(csv_path):
    """Groups rows by pair_id -> {"INTERNAL_BOOK": [...], "CUSTODIAN_CONFIRM": [...]}"""
    pairs = defaultdict(lambda: defaultdict(list))
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            pairs[row["pair_id"]][row["source"]].append(row)
    return pairs


def tier1_exact_match(internal, custodian):
    return all(internal[f] == custodian[f] for f in FIELDS_TO_COMPARE)


def tier2_tolerance_match(internal, custodian):
    if internal["symbol"] != custodian["symbol"]:
        return False
    if internal["counterparty"] != custodian["counterparty"]:
        return False
    if internal["quantity"] != custodian["quantity"]:
        return False

    price_i, price_c = float(internal["price"]), float(custodian["price"])
    price_delta_pct = abs(price_c - price_i) / price_i * 100
    if price_delta_pct > PRICE_TOLERANCE_PCT:
        return False

    date_delta = abs((_parse_date(custodian["settlement_date"])
                       - _parse_date(internal["settlement_date"])).days)
    if date_delta > DATE_TOLERANCE_DAYS:
        return False

    return True


def match_pair(sides):
    """sides: {"INTERNAL_BOOK": [...], "CUSTODIAN_CONFIRM": [...]}
    Returns (status, reason)."""
    internal_rows = sides.get("INTERNAL_BOOK", [])
    custodian_rows = sides.get("CUSTODIAN_CONFIRM", [])

    if len(internal_rows) != 1 or len(custodian_rows) != 1:
        return "UNMATCHED", f"expected 1+1 rows, got {len(internal_rows)}+{len(custodian_rows)}"

    internal, custodian = internal_rows[0], custodian_rows[0]

    if tier1_exact_match(internal, custodian):
        return "MATCHED_TIER1", "exact match"
    if tier2_tolerance_match(internal, custodian):
        return "MATCHED_TIER2", "within tolerance"
    return "UNMATCHED", "outside tolerance"


def run_matching(csv_path):
    """Returns a list of {pair_id, status, reason} for every pair in the file."""
    pairs = load_pairs(csv_path)
    results = []
    for pair_id, sides in pairs.items():
        status, reason = match_pair(sides)
        results.append({"pair_id": pair_id, "status": status, "reason": reason})
    return results


if __name__ == "__main__":
    import sys
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "../../data/test.csv"
    results = run_matching(csv_path)

    counts = defaultdict(int)
    for r in results:
        counts[r["status"]] += 1

    total = len(results)
    print(f"Matched {total} pairs from {csv_path}")
    for status in ["MATCHED_TIER1", "MATCHED_TIER2", "UNMATCHED"]:
        n = counts[status]
        print(f"  {status:<15} {n:>5} ({n/total:.1%})")
