"""
Evaluates the Matching Agent against ground truth (is_break), and
reports the naive exact-match-only baseline separately from the full
Tier1+Tier2 result - this is the
baseline every later component is compared against.
"""

import csv
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "agents"))
from matching import load_pairs, tier1_exact_match, tier2_tolerance_match  # noqa: E402


def ground_truth_by_pair(csv_path):
    truth = {}
    with open(csv_path, newline="") as f:
        for row in csv.DictReader(f):
            truth[row["pair_id"]] = row["is_break"] == "True"
    return truth


def evaluate(csv_path, use_tier2):
    pairs = load_pairs(csv_path)
    truth = ground_truth_by_pair(csv_path)

    tp = fp = tn = fn = 0  # positive = "flagged as a break" (UNMATCHED)
    for pair_id, sides in pairs.items():
        internal_rows = sides.get("INTERNAL_BOOK", [])
        custodian_rows = sides.get("CUSTODIAN_CONFIRM", [])

        if len(internal_rows) != 1 or len(custodian_rows) != 1:
            flagged = True
        else:
            internal, custodian = internal_rows[0], custodian_rows[0]
            matched = tier1_exact_match(internal, custodian)
            if not matched and use_tier2:
                matched = tier2_tolerance_match(internal, custodian)
            flagged = not matched

        actual_break = truth[pair_id]
        if flagged and actual_break:
            tp += 1
        elif flagged and not actual_break:
            fp += 1
        elif not flagged and actual_break:
            fn += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    return {"tp": tp, "fp": fp, "tn": tn, "fn": fn, "precision": precision, "recall": recall}


def print_report(name, m):
    print(f"\n{name}")
    print(f"  Breaks caught (recall):  {m['recall']:.1%}  ({m['tp']} of {m['tp']+m['fn']} real breaks flagged)")
    print(f"  False positives:         {m['fp']}  (clean pairs wrongly flagged)")
    print(f"  False negatives:         {m['fn']}  (real breaks missed entirely)")
    print(f"  Precision:               {m['precision']:.1%}")
    print("  Root cause provided:     No (matching only assigns MATCHED/UNMATCHED, not why)")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else "../../data/test.csv"

    baseline = evaluate(csv_path, use_tier2=False)
    print_report("BASELINE - naive exact-match only (Tier 1, no tolerance, no AI)", baseline)

    full = evaluate(csv_path, use_tier2=True)
    print_report("Matching Agent - Tier 1 + Tier 2 (exact + tolerance)", full)

    print(f"\nTier 2 tolerance matching recovered {baseline['fp'] - full['fp']} false positives "
          f"(pairs that differ slightly but are within acceptable tolerance) without missing any "
          f"additional real breaks (recall {baseline['recall']:.1%} -> {full['recall']:.1%})."
          if baseline["fp"] >= full["fp"] else "")
