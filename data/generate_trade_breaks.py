"""
generate_trade_breaks.py (v7 / Resolvia rewrite)

Generates the Resolvia operational data universe. Replaces the old single "two-sided pair" model with five
relational tables:

  trades              - one row per trade: the canonical/booked (internal) view
  positions           - one row per trade: the observed (external/custodian) position
  cash_transactions   - one or more rows per trade: the observed cash movement(s)
  settlements         - one row per trade: the observed settlement state
  breaks              - one row per trade THAT HAS A BREAK: family + root cause +
                         source/target values + severity + metadata

Design (see Open Issue #3 in the v7 plan): this generator plays the role of
"the reconciliation engine that already exists at the bank" - it produces
BREAK INPUT, the same job backend/agents/matching.py used to do. matching.py
itself is repurposed as a break-feed generator utility rather than deleted;
this script is the more direct/controllable way to build the labeled dataset
since ground truth needs to be known, not detected.

Every trade gets exactly one row in each of positions/cash_transactions(*)/
settlements, matching the trade's expected values when clean. ~15-20% of
trades get exactly one root cause injected (see taxonomy.py), which perturbs
whichever table that root cause belongs to and produces one breaks row.
TRADE-family breaks (including the two CONF_* confirmation causes) have no
separate "external confirmation" table - the discrepancy is carried directly
on the breaks row's source_value/target_value, consistent with the
"we begin at BREAK INPUT, we don't rebuild a matching engine" framing.

(*) CASH_MISSING_ENTRY produces zero cash_transactions rows for that trade;
CASH_DUPLICATE_ENTRY produces two. Every other case produces exactly one.

USAGE: python generate_trade_breaks.py
OUTPUTS (all in this directory): trades.csv, positions.csv,
  cash_transactions.csv, settlements.csv, breaks.csv - each with a `split`
  column (TRAIN/TEST), split by trade_id (80/20).
"""

import csv
import random
from datetime import datetime, timedelta

from taxonomy import ROOT_CAUSES, CA_ROOT_CAUSES, CORPORATE_ACTION_TYPE, validate_taxonomy

random.seed(42)
validate_taxonomy()

# ---------------------------------------------------------------------
# STEP 1: clean trade universe (unchanged in spirit from v6 - swap
# load_clean_trades() for a real NSE bhavcopy loader before the final demo)
# ---------------------------------------------------------------------

DEMO_SYMBOLS = [
    ("RELIANCE", 2850.50), ("TCS", 4120.75), ("INFY", 1890.30),
    ("HDFCBANK", 1675.20), ("ICICIBANK", 1240.80), ("SBIN", 845.60),
    ("BHARTIARTL", 1690.40), ("ITC", 468.90), ("LT", 3680.15),
    ("AXISBANK", 1180.25), ("KOTAKBANK", 1955.70), ("WIPRO", 610.35),
    ("HINDUNILVR", 2745.60), ("MARUTI", 12980.00), ("TATASTEEL", 172.45),
]

COUNTERPARTIES = ["ICICI-CUST", "HDFC-CUST", "KOTAK-CUST", "DEUTSCHE-BROKER",
                   "MORGANSTANLEY-BROKER", "NOMURA-BROKER"]

# expected SSI per counterparty (used by SETL_WRONG_SSI) - deliberately not
# alphabetically/numerically adjacent so a wrong SSI can't be mistaken for a
# rounding artifact.
EXPECTED_SSI = {
    "ICICI-CUST": "SSI-IN-0091", "HDFC-CUST": "SSI-IN-0147",
    "KOTAK-CUST": "SSI-IN-0203", "DEUTSCHE-BROKER": "SSI-DE-5510",
    "MORGANSTANLEY-BROKER": "SSI-US-7742", "NOMURA-BROKER": "SSI-JP-3389",
}

PORTFOLIOS = ["EQ-CORE-01", "EQ-CORE-02", "EQ-ALPHA-03", "EQ-INDEX-04"]

CA_RATIOS = [1.5, 2.0, 3.0]  # clean, round ratios - a real split/bonus, not noise


def load_clean_trades(n=3000):
    trades = []
    base_date = datetime(2026, 8, 1)
    for i in range(n):
        symbol, px = random.choice(DEMO_SYMBOLS)
        qty = random.choice([100, 200, 250, 500, 750, 1000, 1500, 2000])
        price = round(px * random.uniform(0.995, 1.005), 2)
        trade_date = base_date + timedelta(days=random.randint(0, 20))
        settlement_date = trade_date + timedelta(days=1)  # T+1 in India
        counterparty = random.choice(COUNTERPARTIES)
        trades.append({
            "trade_id": f"TRD{100000+i}",
            "trade_date": trade_date.strftime("%Y-%m-%d"),
            "security": symbol,
            "isin": f"INE{100000+i:06d}",
            "ticker": symbol,
            "quantity": qty,
            "price": price,
            "trade_value": round(qty * price, 2),
            "counterparty": counterparty,
            "portfolio": random.choice(PORTFOLIOS),
            "booking_status": "BOOKED",
            "settlement_date": settlement_date.strftime("%Y-%m-%d"),
            "side": random.choice(["BUY", "SELL"]),
            # external confirmation view - defaults to agreeing with the
            # booked values; TRADE-family injectors below mutate these.
            # Without this, TRADE-family breaks would only be detectable by
            # reading the breaks row itself (the label), not by observing
            # anything independent - see the comment on TRADE_ONLY_INJECTORS.
            "confirmed_price": price, "confirmed_quantity": qty,
            "confirmed_trade_date": trade_date.strftime("%Y-%m-%d"),
            "confirmed_counterparty": counterparty,
            "confirmation_status": "RECEIVED",
        })
    return trades


# ---------------------------------------------------------------------
# STEP 2: per-family derivation of the "observed" tables, and break
# injection. One function per root cause keeps each injection rule
# self-contained and independently readable/testable.
# ---------------------------------------------------------------------

def _date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def _fmt(d):
    return d.strftime("%Y-%m-%d")


def derive_clean_position(trade, pos_id):
    return {
        "position_id": pos_id, "trade_id": trade["trade_id"],
        "security": trade["security"], "portfolio": trade["portfolio"],
        "expected_quantity": trade["quantity"], "actual_quantity": trade["quantity"],
        "as_of_date": trade["settlement_date"], "source": "CUSTODIAN",
    }


def derive_clean_cash(trade, cash_id):
    return {
        "cash_id": cash_id, "trade_id": trade["trade_id"],
        "account": f"ACC-{trade['portfolio']}", "currency": "INR",
        "amount": trade["trade_value"], "expected_amount": trade["trade_value"],
        "value_date": trade["settlement_date"], "transaction_type": "SETTLEMENT",
        "status": "MATCHED",
    }


def derive_clean_settlement(trade, settle_id):
    return {
        "settlement_id": settle_id, "trade_id": trade["trade_id"],
        "settlement_date": trade["settlement_date"], "settlement_status": "SETTLED",
        "instruction_status": "INSTRUCTED", "custodian": trade["counterparty"],
        "quantity": trade["quantity"], "amount": trade["trade_value"],
        "ssi_code": EXPECTED_SSI[trade["counterparty"]],
    }


# --- POSITION-family injections (mutate the position row) ---

def inject_pos_missing_booking(trade, position):
    position["actual_quantity"] = 0
    position["source"] = "MISSING"
    return {"source_value": trade["quantity"], "target_value": 0, "breaking_fields": "actual_quantity"}


def inject_pos_wrong_quantity(trade, position):
    delta_pct = random.choice([-0.31, -0.22, -0.13, 0.17, 0.24, 0.29])  # non-round on purpose
    new_qty = max(1, round(trade["quantity"] * (1 + delta_pct)))
    position["actual_quantity"] = new_qty
    return {"source_value": trade["quantity"], "target_value": new_qty, "breaking_fields": "actual_quantity"}


def inject_pos_timing_difference(trade, position):
    position["as_of_date"] = _fmt(_date(trade["settlement_date"]) + timedelta(days=1))
    return {"source_value": trade["settlement_date"], "target_value": position["as_of_date"],
            "breaking_fields": "as_of_date"}


def inject_ca_incorrect_entitlement(trade, position):
    correct_ratio = random.choice(CA_RATIOS)
    wrong_ratio = correct_ratio + random.choice([-0.2, 0.2, -0.3, 0.3])
    position["actual_quantity"] = round(trade["quantity"] * wrong_ratio)
    return {"source_value": round(trade["quantity"] * correct_ratio), "target_value": position["actual_quantity"],
            "breaking_fields": "actual_quantity"}


def inject_ca_mandatory_not_reflected(trade, position):
    ratio = random.choice(CA_RATIOS)
    position["actual_quantity"] = trade["quantity"]  # split/bonus ratio never applied externally
    return {"source_value": round(trade["quantity"] * ratio), "target_value": trade["quantity"],
            "breaking_fields": "actual_quantity"}


def inject_ca_voluntary_decision(trade, position):
    # Deliberately the same structural signature as CA_MANDATORY_NOT_REFLECTED -
    # telling these two apart is supposed to require the corporate action
    # notice (Week 2+ document evidence), not the structured deltas alone.
    ratio = random.choice(CA_RATIOS)
    position["actual_quantity"] = trade["quantity"]
    return {"source_value": round(trade["quantity"] * ratio), "target_value": trade["quantity"],
            "breaking_fields": "actual_quantity"}


# --- CASH-family injections (mutate cash row list) ---

def inject_cash_missing_entry(trade, cash_rows):
    removed = cash_rows.pop()
    return {"source_value": trade["trade_value"], "target_value": None, "breaking_fields": "amount"}


def inject_cash_duplicate_entry(trade, cash_rows, next_cash_id):
    dup = dict(cash_rows[0])
    dup["cash_id"] = next_cash_id
    cash_rows.append(dup)
    return {"source_value": trade["trade_value"], "target_value": trade["trade_value"] * 2,
            "breaking_fields": "amount,cash_id"}


def inject_cash_wrong_amount(trade, cash_rows):
    delta_pct = random.choice([-0.18, -0.09, 0.11, 0.19, 0.27])  # non-round
    new_amt = round(trade["trade_value"] * (1 + delta_pct), 2)
    cash_rows[0]["amount"] = new_amt
    return {"source_value": trade["trade_value"], "target_value": new_amt, "breaking_fields": "amount"}


def inject_cash_fx_input_difference(trade, cash_rows):
    fx_rate = random.choice([1.02, 1.035, 1.05, 1.07, 0.96, 0.93])  # plausible stale/wrong FX rate
    new_amt = round(trade["trade_value"] * fx_rate, 2)
    cash_rows[0]["amount"] = new_amt
    cash_rows[0]["currency"] = random.choice(["USD", "EUR", "GBP"])
    return {"source_value": trade["trade_value"], "target_value": new_amt,
            "breaking_fields": "amount,currency"}


# --- SETTLEMENT-family injections (mutate settlement row) ---

def inject_setl_wrong_ssi(trade, settlement):
    correct_ssi = EXPECTED_SSI[trade["counterparty"]]
    wrong_ssi = random.choice([s for s in EXPECTED_SSI.values() if s != correct_ssi])
    settlement["ssi_code"] = wrong_ssi
    settlement["settlement_status"] = "FAILED"
    settlement["instruction_status"] = "INCORRECT"
    return {"source_value": correct_ssi, "target_value": wrong_ssi, "breaking_fields": "ssi_code"}


def inject_setl_late_counterparty(trade, settlement):
    delay = random.choice([2, 3, 4, 5])
    settlement["settlement_date"] = _fmt(_date(trade["settlement_date"]) + timedelta(days=delay))
    settlement["settlement_status"] = "PENDING"
    return {"source_value": trade["settlement_date"], "target_value": settlement["settlement_date"],
            "breaking_fields": "settlement_date,settlement_status"}


def inject_setl_missing_instruction(trade, settlement):
    settlement["instruction_status"] = "MISSING"
    settlement["settlement_status"] = "PENDING"
    settlement["ssi_code"] = None
    return {"source_value": "INSTRUCTED", "target_value": "MISSING", "breaking_fields": "instruction_status"}


def inject_setl_incorrect_date(trade, settlement):
    settlement["settlement_date"] = _fmt(_date(trade["settlement_date"]) + timedelta(days=1))
    # status stays SETTLED - it did settle, just logged against the wrong date
    return {"source_value": trade["settlement_date"], "target_value": settlement["settlement_date"],
            "breaking_fields": "settlement_date"}


# --- TRADE-family injections ---
# These mutate the trade's own confirmed_* fields (the "external
# confirmation" view added in load_clean_trades) rather than just
# returning a delta for the breaks row. Without that, the only place a
# TRADE-family discrepancy would exist is the breaks row itself - which
# is the label. A classifier fit on breaks.source_value/target_value
# would be reading the answer, not learning anything.

def inject_trade_price_mismatch(trade):
    delta_pct = random.uniform(0.011, 0.03) * random.choice([-1, 1])
    confirmed = round(trade["price"] * (1 + delta_pct), 2)
    trade["confirmed_price"] = confirmed
    return {"source_value": trade["price"], "target_value": confirmed, "breaking_fields": "price"}


def inject_trade_quantity_mismatch(trade):
    delta = random.choice([-100, -50, 50, 100, 200])
    confirmed = max(1, trade["quantity"] + delta)
    trade["confirmed_quantity"] = confirmed
    return {"source_value": trade["quantity"], "target_value": confirmed, "breaking_fields": "quantity"}


def inject_trade_date_mismatch(trade):
    confirmed = _fmt(_date(trade["trade_date"]) + timedelta(days=1))
    trade["confirmed_trade_date"] = confirmed
    return {"source_value": trade["trade_date"], "target_value": confirmed, "breaking_fields": "trade_date"}


def inject_trade_counterparty_id_mismatch(trade):
    confirmed = random.choice([c for c in COUNTERPARTIES if c != trade["counterparty"]])
    trade["confirmed_counterparty"] = confirmed
    return {"source_value": trade["counterparty"], "target_value": confirmed, "breaking_fields": "counterparty"}


def inject_conf_missing(trade):
    trade["confirmation_status"] = "MISSING"
    trade["confirmed_price"] = None
    trade["confirmed_quantity"] = None
    trade["confirmed_trade_date"] = None
    trade["confirmed_counterparty"] = None
    return {"source_value": trade["trade_id"], "target_value": None, "breaking_fields": "confirmation"}


def inject_conf_disagreement(trade):
    confirmed_qty = trade["quantity"] + random.choice([-75, 75])
    confirmed_price = round(trade["price"] * random.uniform(1.01, 1.02), 2)
    trade["confirmed_quantity"] = confirmed_qty
    trade["confirmed_price"] = confirmed_price
    return {"source_value": f"qty={trade['quantity']},price={trade['price']}",
            "target_value": f"qty={confirmed_qty},price={confirmed_price}",
            "breaking_fields": "quantity,price"}


TRADE_ONLY_INJECTORS = {
    "TRADE_PRICE_MISMATCH": inject_trade_price_mismatch,
    "TRADE_QUANTITY_MISMATCH": inject_trade_quantity_mismatch,
    "TRADE_DATE_MISMATCH": inject_trade_date_mismatch,
    "TRADE_COUNTERPARTY_ID_MISMATCH": inject_trade_counterparty_id_mismatch,
    "CONF_MISSING": inject_conf_missing,
    "CONF_DISAGREEMENT": inject_conf_disagreement,
}

POSITION_INJECTORS = {
    "POS_MISSING_BOOKING": inject_pos_missing_booking,
    "POS_WRONG_QUANTITY": inject_pos_wrong_quantity,
    "POS_TIMING_DIFFERENCE": inject_pos_timing_difference,
    "CA_INCORRECT_ENTITLEMENT": inject_ca_incorrect_entitlement,
    "CA_MANDATORY_NOT_REFLECTED": inject_ca_mandatory_not_reflected,
    "CA_VOLUNTARY_DECISION": inject_ca_voluntary_decision,
}

SETTLEMENT_INJECTORS = {
    "SETL_WRONG_SSI": inject_setl_wrong_ssi,
    "SETL_LATE_COUNTERPARTY": inject_setl_late_counterparty,
    "SETL_MISSING_INSTRUCTION": inject_setl_missing_instruction,
    "SETL_INCORRECT_DATE": inject_setl_incorrect_date,
}

# CASH injectors handled separately below - they need row-list surgery
# (add/remove rows), not a single dict mutation, so they don't fit the
# same one-arg-mutates-in-place shape as the others.


# ---------------------------------------------------------------------
# STEP 3: assemble the five tables
# ---------------------------------------------------------------------

def _stratified_root_causes(n_breaks):
    """Deterministic near-even coverage across all 20 root causes, rather
    than relying on uniform random draw to even out over a large sample.
    floor(n_breaks/20) of each cause, remainder distributed round-robin,
    then shuffled so assignment order doesn't correlate with trade_id
    order. At n_breaks=3000 this is exactly 150/cause."""
    keys = list(ROOT_CAUSES.keys())
    base, remainder = divmod(n_breaks, len(keys))
    causes = keys * base + keys[:remainder]
    random.shuffle(causes)
    return causes


def build_dataset(trades, break_rate=0.175):
    positions, cash_txns, settlements, breaks = [], [], [], []
    pos_id, cash_id, settle_id, break_id = 1, 1, 1, 1

    # decide which trades break, and which root cause each gets - stratified
    # so every root cause gets proportional representation regardless of
    # break_rate, instead of leaving thin classes to random variance.
    n_breaks = round(len(trades) * break_rate)
    breaking_trade_ids = random.sample([t["trade_id"] for t in trades], n_breaks)
    causes_for_breaks = _stratified_root_causes(n_breaks)
    root_cause_by_trade = dict(zip(breaking_trade_ids, causes_for_breaks))
    breaking_trade_ids = set(breaking_trade_ids)

    for trade in trades:
        position = derive_clean_position(trade, pos_id); pos_id += 1
        cash_rows = [derive_clean_cash(trade, cash_id)]; cash_id += 1
        settlement = derive_clean_settlement(trade, settle_id); settle_id += 1

        is_break = trade["trade_id"] in breaking_trade_ids
        root_cause = root_cause_by_trade.get(trade["trade_id"]) if is_break else None

        if is_break:
            meta = ROOT_CAUSES[root_cause]
            family = meta["family"]

            if root_cause in POSITION_INJECTORS:
                delta = POSITION_INJECTORS[root_cause](trade, position)
            elif root_cause in SETTLEMENT_INJECTORS:
                delta = SETTLEMENT_INJECTORS[root_cause](trade, settlement)
            elif root_cause == "CASH_MISSING_ENTRY":
                delta = inject_cash_missing_entry(trade, cash_rows)
            elif root_cause == "CASH_DUPLICATE_ENTRY":
                delta = inject_cash_duplicate_entry(trade, cash_rows, cash_id); cash_id += 1
            elif root_cause == "CASH_WRONG_AMOUNT":
                delta = inject_cash_wrong_amount(trade, cash_rows)
            elif root_cause == "CASH_FX_INPUT_DIFFERENCE":
                delta = inject_cash_fx_input_difference(trade, cash_rows)
            elif root_cause in TRADE_ONLY_INJECTORS:
                delta = TRADE_ONLY_INJECTORS[root_cause](trade)
            else:
                raise ValueError(f"no injector wired for root cause {root_cause}")

            breaks.append({
                "break_id": f"BRK{break_id:05d}", "reconciliation_id": "RECON-DAILY",
                "business_date": trade["settlement_date"], "break_type": family,
                "mismatch_type": root_cause, "root_cause": meta["description"],
                "source_system": "INTERNAL_BOOK",
                "comparison_system": "CUSTODIAN_CONFIRM" if family != "TRADE" else "EXTERNAL_CONFIRMATION",
                "source_record_id": trade["trade_id"],
                "comparison_record_id": trade["trade_id"],
                "source_value": delta["source_value"], "target_value": delta["target_value"],
                "difference": None, "breaking_fields": delta["breaking_fields"],
                "severity": meta["severity"], "status": "OPEN", "age": 0,
                "counterparty": trade["counterparty"], "client": trade["portfolio"],
                "corporate_action_type": CORPORATE_ACTION_TYPE.get(root_cause, ""),
                "needs_evidence_bundle": False,  # set below for a sampled subset
            })
            break_id += 1

        positions.append(position)
        cash_txns.extend(cash_rows)
        settlements.append(settlement)

    # Evidence-bundle rule (per-family, not a flat sample): CA, SETTLEMENT
    # and TRADE breaks get a document for every occurrence - this mirrors
    # real workflows where a contract note / settlement message / CA
    # notice is generated for every relevant event, not sampled. POSITION
    # (non-CA) and CASH breaks get a ~25% sample, since an ops note only
    # exists when someone thought to write one.
    SAMPLE_RATE = 0.25
    chosen_ids = set()
    non_ca_position = [b for b in breaks if b["break_type"] == "POSITION" and not b["corporate_action_type"]]
    cash = [b for b in breaks if b["break_type"] == "CASH"]
    random.shuffle(non_ca_position)
    random.shuffle(cash)
    for b in breaks:
        if b["corporate_action_type"] or b["break_type"] in ("SETTLEMENT", "TRADE"):
            chosen_ids.add(b["break_id"])
    for b in non_ca_position[:round(len(non_ca_position) * SAMPLE_RATE)]:
        chosen_ids.add(b["break_id"])
    for b in cash[:round(len(cash) * SAMPLE_RATE)]:
        chosen_ids.add(b["break_id"])
    for b in breaks:
        b["needs_evidence_bundle"] = b["break_id"] in chosen_ids

    return positions, cash_txns, settlements, breaks


# ---------------------------------------------------------------------
# STEP 4: write CSVs with a `split` column (TRAIN/TEST by trade_id)
# ---------------------------------------------------------------------

def write_csv(path, rows, fieldnames):
    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for r in rows:
            writer.writerow({k: r.get(k, "") for k in fieldnames})


if __name__ == "__main__":
    # n=6000 / break_rate=0.50 (scaled-up dataset): deliberately
    # inflated break rate vs. real production reconciliation (~1-5%) to
    # densify per-root-cause training/test examples to 150 each (stratified,
    # see _stratified_root_causes) - a training-data density choice, not a
    # claim about realistic break incidence. Document/evidence realism is
    # handled separately (generate_broker_confirms.py's SWIFT/NSE-grounded
    # templates), independent of this volume choice.
    trades = load_clean_trades(n=6000)
    positions, cash_txns, settlements, breaks = build_dataset(trades, break_rate=0.50)

    # split by trade_id - sorted(set(...)) before shuffle for determinism
    # (see v6's hard-won bug fix: raw set() iteration order depends on
    # per-process hash randomization even with a fixed random.seed()).
    trade_ids = sorted({t["trade_id"] for t in trades})
    random.shuffle(trade_ids)
    split_idx = int(len(trade_ids) * 0.8)
    train_ids, test_ids = set(trade_ids[:split_idx]), set(trade_ids[split_idx:])

    def split_of(trade_id):
        return "TRAIN" if trade_id in train_ids else "TEST"

    for t in trades:
        t["split"] = split_of(t["trade_id"])
    for p in positions:
        p["split"] = split_of(p["trade_id"])
    for c in cash_txns:
        c["split"] = split_of(c["trade_id"])
    for s in settlements:
        s["split"] = split_of(s["trade_id"])
    for b in breaks:
        b["split"] = split_of(b["source_record_id"])

    write_csv("trades.csv", trades, [
        "trade_id", "trade_date", "security", "isin", "ticker", "quantity", "price",
        "trade_value", "counterparty", "portfolio", "booking_status", "settlement_date",
        "side", "confirmed_price", "confirmed_quantity", "confirmed_trade_date",
        "confirmed_counterparty", "confirmation_status", "split"])
    write_csv("positions.csv", positions, [
        "position_id", "trade_id", "security", "portfolio", "expected_quantity",
        "actual_quantity", "as_of_date", "source", "split"])
    write_csv("cash_transactions.csv", cash_txns, [
        "cash_id", "trade_id", "account", "currency", "amount", "expected_amount",
        "value_date", "transaction_type", "status", "split"])
    write_csv("settlements.csv", settlements, [
        "settlement_id", "trade_id", "settlement_date", "settlement_status",
        "instruction_status", "custodian", "quantity", "amount", "ssi_code", "split"])
    write_csv("breaks.csv", breaks, [
        "break_id", "reconciliation_id", "business_date", "break_type", "mismatch_type",
        "root_cause", "source_system", "comparison_system", "source_record_id",
        "comparison_record_id", "source_value", "target_value", "difference",
        "breaking_fields", "severity", "status", "age", "counterparty", "client",
        "corporate_action_type", "needs_evidence_bundle", "split"])

    print(f"Trades: {len(trades)} ({len(train_ids)} train / {len(test_ids)} test)")
    print(f"Breaks: {len(breaks)} ({len(breaks)/len(trades):.1%})")
    print(f"Evidence-bundle breaks: {sum(1 for b in breaks if b['needs_evidence_bundle'])}")
    from collections import Counter
    fam_counts = Counter(b["break_type"] for b in breaks)
    rc_counts = Counter(b["mismatch_type"] for b in breaks)
    print("By family:", dict(fam_counts))
    print(f"Root causes represented: {len(rc_counts)} / {len(ROOT_CAUSES)}")
