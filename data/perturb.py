"""
Makes the clean synthetic data messier, for stress testing.

The generator gives every broken trade exactly one clean fault. Real breaks
are not that tidy, so this module can add two kinds of mess to the records
before features are built:

  jitter        small random noise on confirmed prices and posted cash
                amounts, like rounding, fees or a slightly stale rate. With
                enough of it, a genuine price mismatch and plain noise start
                to look alike.
  multi_cause   a second, unrelated fault on the same trade, taken from a
                different break family and injected with the generator's own
                functions. The break feed still reports the first one.

Everything runs on copies of the tables and is seeded, so a stress test is
repeatable.
"""

import random

import numpy as np
import pandas as pd

import generate_trade_breaks as gen
from taxonomy import ROOT_CAUSES


def _second_cause_for(primary, rnd):
    family = ROOT_CAUSES[primary]["family"]
    options = [rc for rc, meta in ROOT_CAUSES.items() if meta["family"] != family]
    return rnd.choice(options)


def _inject(cause, trade, position, cash_rows, settlement, next_cash_id):
    if cause in gen.POSITION_INJECTORS:
        gen.POSITION_INJECTORS[cause](trade, position)
    elif cause in gen.SETTLEMENT_INJECTORS:
        gen.SETTLEMENT_INJECTORS[cause](trade, settlement)
    elif cause in gen.TRADE_ONLY_INJECTORS:
        gen.TRADE_ONLY_INJECTORS[cause](trade)
    elif cause == "CASH_MISSING_ENTRY":
        if cash_rows:
            gen.inject_cash_missing_entry(trade, cash_rows)
    elif cause == "CASH_DUPLICATE_ENTRY":
        if cash_rows:
            gen.inject_cash_duplicate_entry(trade, cash_rows, next_cash_id)
    elif cause == "CASH_WRONG_AMOUNT":
        if cash_rows:
            gen.inject_cash_wrong_amount(trade, cash_rows)
    elif cause == "CASH_FX_INPUT_DIFFERENCE":
        if cash_rows:
            gen.inject_cash_fx_input_difference(trade, cash_rows)


def perturb(frames, jitter=0.0, multi_cause=0.0, split=None, seed=0):
    """Returns a new dict of frames. breaks gets a second_cause column (blank
    when there isn't one); it is only ever used for scoring."""
    rnd = random.Random(seed)
    rng = np.random.default_rng(seed)
    # the generator's injectors draw from the module-level random
    random.seed(seed)

    trades = {r["trade_id"]: r for r in frames["trades"].to_dict("records")}
    positions = {r["trade_id"]: r for r in frames["positions"].to_dict("records")}
    settlements = {r["trade_id"]: r for r in frames["settlements"].to_dict("records")}
    cash = {}
    for r in frames["cash_transactions"].to_dict("records"):
        cash.setdefault(r["trade_id"], []).append(r)
    breaks = frames["breaks"].to_dict("records")
    next_cash_id = int(frames["cash_transactions"]["cash_id"].max()) + 1

    in_scope = {tid for tid, t in trades.items() if split is None or t["split"] == split}

    if jitter > 0:
        for tid in in_scope:
            t = trades[tid]
            if pd.notna(t["confirmed_price"]):
                t["confirmed_price"] = round(float(t["confirmed_price"]) * (1 + rng.normal(0, jitter)), 2)
            for c in cash.get(tid, []):
                c["amount"] = round(float(c["amount"]) * (1 + rng.normal(0, jitter)), 2)

    for b in breaks:
        b["second_cause"] = ""
        tid = b["source_record_id"]
        if tid not in in_scope or multi_cause <= 0 or rnd.random() >= multi_cause:
            continue
        second = _second_cause_for(b["mismatch_type"], rnd)
        cash.setdefault(tid, [])
        _inject(second, trades[tid], positions[tid], cash[tid], settlements[tid], next_cash_id)
        next_cash_id += 1
        b["second_cause"] = second

    return {
        "trades": pd.DataFrame(trades.values()),
        "positions": pd.DataFrame(positions.values()),
        "settlements": pd.DataFrame(settlements.values()),
        "cash_transactions": pd.DataFrame([c for rows in cash.values() for c in rows]),
        "breaks": pd.DataFrame(breaks),
    }


OCR_CONFUSIONS = {"O": "0", "0": "O", "I": "1", "1": "I", "L": "1", "S": "5", "5": "S",
                  "B": "8", "8": "B", "A": "4", "E": "F", "U": "V", "V": "U", "M": "N", "N": "M"}


def ocr_noise(text, char_error_rate, seed=0):
    """Mimics a poor scan: each letter or digit is swapped for a look-alike
    (or a random character) with the given probability."""
    if not text or char_error_rate <= 0:
        return text
    rnd = random.Random(seed)
    out = []
    for ch in text:
        if ch.isalnum() and rnd.random() < char_error_rate:
            up = ch.upper()
            out.append(OCR_CONFUSIONS.get(up, rnd.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")))
        else:
            out.append(ch)
    return "".join(out)
