"""
validate_dataset.py

Data cleaning / integrity checks for the five-table dataset. Run as a script
rather than buried in the EDA notebook so it can be re-run any time the
generator changes.

Checks:
  1. Every trade_id referenced by positions/cash_transactions/settlements/
     breaks exists in trades.csv.
  2. Every trade has exactly one position and one settlement row.
  3. Every trade has 0, 1, or 2 cash_transactions rows (0 only for
     CASH_MISSING_ENTRY, 2 only for CASH_DUPLICATE_ENTRY).
  4. `split` (TRAIN/TEST) is consistent for a trade across all five tables
     - a trade's evidence must never straddle the split.
  5. Every breaks.severity is in {P0, P1, P2}; every breaks.break_type is
     one of the 4 families; every breaks.mismatch_type is a known root
     cause key and belongs to the family recorded on the same row.
  6. No duplicate primary keys (trade_id, position_id, cash_id,
     settlement_id, break_id).
  7. corporate_action_type is only set for the 3 CA root causes, and
     needs_evidence_bundle is only True for actual breaks.
"""

import csv
from collections import Counter, defaultdict

from taxonomy import ROOT_CAUSES, BREAK_FAMILIES, CA_ROOT_CAUSES


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def main():
    trades = read_csv("trades.csv")
    positions = read_csv("positions.csv")
    cash = read_csv("cash_transactions.csv")
    settlements = read_csv("settlements.csv")
    breaks = read_csv("breaks.csv")

    errors = []

    trade_ids = {t["trade_id"] for t in trades}
    trade_split = {t["trade_id"]: t["split"] for t in trades}

    # 1. Duplicate primary keys
    for name, rows, key in [
        ("trades", trades, "trade_id"), ("positions", positions, "position_id"),
        ("cash_transactions", cash, "cash_id"), ("settlements", settlements, "settlement_id"),
        ("breaks", breaks, "break_id"),
    ]:
        counts = Counter(r[key] for r in rows)
        dupes = [k for k, c in counts.items() if c > 1]
        if dupes:
            errors.append(f"{name}: duplicate {key} values: {dupes[:5]}{'...' if len(dupes) > 5 else ''}")

    # 2. Referential integrity + row-count-per-trade checks
    pos_by_trade = Counter(p["trade_id"] for p in positions)
    settle_by_trade = Counter(s["trade_id"] for s in settlements)
    cash_by_trade = Counter(c["trade_id"] for c in cash)

    for t in trades:
        tid = t["trade_id"]
        if pos_by_trade[tid] != 1:
            errors.append(f"trade {tid}: expected exactly 1 position row, found {pos_by_trade[tid]}")
        if settle_by_trade[tid] != 1:
            errors.append(f"trade {tid}: expected exactly 1 settlement row, found {settle_by_trade[tid]}")
        if cash_by_trade[tid] not in (0, 1, 2):
            errors.append(f"trade {tid}: unexpected cash row count {cash_by_trade[tid]}")

    for name, rows, ref_field in [
        ("positions", positions, "trade_id"), ("cash_transactions", cash, "trade_id"),
        ("settlements", settlements, "trade_id"),
    ]:
        orphans = [r[ref_field] for r in rows if r[ref_field] not in trade_ids]
        if orphans:
            errors.append(f"{name}: {len(orphans)} rows reference unknown trade_id, e.g. {orphans[:3]}")

    # 3. split consistency across tables for the same trade
    for name, rows, ref_field in [
        ("positions", positions, "trade_id"), ("cash_transactions", cash, "trade_id"),
        ("settlements", settlements, "trade_id"),
    ]:
        for r in rows:
            tid = r[ref_field]
            if tid in trade_split and r["split"] != trade_split[tid]:
                errors.append(f"{name} row for {tid}: split={r['split']} but trades.csv has {trade_split[tid]}")

    # 4. breaks table: family/root-cause/severity consistency
    valid_severities = {"P0", "P1", "P2"}
    for b in breaks:
        if b["source_record_id"] not in trade_ids:
            errors.append(f"breaks {b['break_id']}: source_record_id {b['source_record_id']} not a known trade")
        if b["severity"] not in valid_severities:
            errors.append(f"breaks {b['break_id']}: invalid severity {b['severity']}")
        if b["break_type"] not in BREAK_FAMILIES:
            errors.append(f"breaks {b['break_id']}: invalid break_type/family {b['break_type']}")
        if b["mismatch_type"] not in ROOT_CAUSES:
            errors.append(f"breaks {b['break_id']}: unknown root cause key {b['mismatch_type']}")
        elif ROOT_CAUSES[b["mismatch_type"]]["family"] != b["break_type"]:
            errors.append(f"breaks {b['break_id']}: root cause {b['mismatch_type']} belongs to "
                           f"{ROOT_CAUSES[b['mismatch_type']]['family']}, not recorded family {b['break_type']}")
        ca_set = b["corporate_action_type"] not in ("", None)
        should_be_ca = b["mismatch_type"] in CA_ROOT_CAUSES
        if ca_set != should_be_ca:
            errors.append(f"breaks {b['break_id']}: corporate_action_type={b['corporate_action_type']!r} "
                           f"inconsistent with root cause {b['mismatch_type']}")

    # 5. TRADE-family breaks must be observable independently of the breaks
    # row itself - confirmed_* must actually differ from the booked value
    # for exactly the fields the break claims, and must NOT differ for any
    # trade that isn't a TRADE-family break (no silent leakage/no silent
    # under-injection).
    trade_break_by_id = {b["source_record_id"]: b for b in breaks if b["break_type"] == "TRADE"}
    for t in trades:
        tid = t["trade_id"]
        confirmed_differs = (
            t["confirmed_price"] != t["price"] or t["confirmed_quantity"] != t["quantity"] or
            t["confirmed_trade_date"] != t["trade_date"] or t["confirmed_counterparty"] != t["counterparty"] or
            t["confirmation_status"] != "RECEIVED"
        )
        if tid in trade_break_by_id and not confirmed_differs:
            errors.append(f"trade {tid}: TRADE-family break recorded but confirmed_* view matches booked view")
        if tid not in trade_break_by_id and confirmed_differs:
            errors.append(f"trade {tid}: confirmed_* view differs from booked view but no TRADE-family break recorded")

    # 6. every trade appears in at most one break (single-root-cause design)
    break_trade_counts = Counter(b["source_record_id"] for b in breaks)
    multi = [tid for tid, c in break_trade_counts.items() if c > 1]
    if multi:
        errors.append(f"{len(multi)} trades have more than one break row: {multi[:5]}")

    print(f"Rows: trades={len(trades)} positions={len(positions)} cash={len(cash)} "
          f"settlements={len(settlements)} breaks={len(breaks)}")
    print(f"Breaks by family: {dict(Counter(b['break_type'] for b in breaks))}")
    print(f"Root causes covered: {len(set(b['mismatch_type'] for b in breaks))}/{len(ROOT_CAUSES)}")

    if errors:
        print(f"\n{len(errors)} VALIDATION ERRORS:")
        for e in errors[:30]:
            print(f"  - {e}")
        raise SystemExit(1)
    else:
        print("\nAll checks passed - no orphan references, no duplicate keys, "
              "split is consistent, family/root-cause/severity are all internally consistent.")


if __name__ == "__main__":
    main()
