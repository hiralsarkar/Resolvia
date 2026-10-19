"""
How much human work does the approval rule cost, and what does it buy?

Two questions, both on the held-out TEST breaks, on clean data and on messy
data (price and cash jitter plus a second fault on 20% of trades):

1. Risk-based approval. Today every controlled action waits for a person.
   I compare that with rules that let small, confident, non-critical fixes go
   straight to execution, still followed by Validation's re-check.
2. Reviewer error. The strict rule assumes the reviewer catches every wrong
   diagnosis. Here reviewers miss a share of them, and I count what
   Validation catches after the fact and what slips through.

The live Control Gate is unchanged; this only measures the trade-off.

Run from backend/:  python eval/approval_policy.py
Writes docs/analysis/approval_policy.md and .json
"""

import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import robustness as R  # noqa: E402
import sim  # noqa: E402
from features import build_features, load_frames, FEATURE_COLS  # noqa: E402
from perturb import perturb  # noqa: E402
from resolution import ACTION_CATALOG  # noqa: E402

POLICIES = {
    "strict (live)": None,
    "auto under 1 lakh": 100_000,
    "auto under 5 lakh": 500_000,
    "auto under 10 lakh": 1_000_000,
}
AUTO_MIN_CONFIDENCE = 0.95
REVIEWER_MISS = [0.0, 0.05, 0.1, 0.2]
DATASETS = {"clean": (0, 0), "messy": (0.005, 0.2), "very messy": (0.01, 0.4)}


def break_rows(frames, models, notice_text, jitter, multi, seed):
    pf = perturb(frames, jitter=jitter, multi_cause=multi, split="TEST", seed=seed) if jitter or multi else \
        dict(frames, breaks=frames["breaks"].assign(second_cause=""))
    feats = build_features(pf).set_index("break_id")
    brk = pf["breaks"][pf["breaks"].split == "TEST"]
    trades = pf["trades"].set_index("trade_id")
    records = sim.records_by_trade(pf)
    preds, conf, _ = R.predict(models["production"], feats.loc[brk.break_id, FEATURE_COLS])
    rows = []
    for (_, b), p, c in zip(brk.iterrows(), preds, conf):
        agent = R.agent_view(p, c, b["corporate_action_type"], notice_text.get(b["break_id"]))
        rows.append({
            "pred": agent, "conf": float(c), "is_ca": R.is_ca(b["corporate_action_type"]),
            "severity": b["severity"], "exposure": float(trades.loc[b["source_record_id"], "trade_value"]),
            "correct": agent in (b["mismatch_type"], b["second_cause"] or b["mismatch_type"]),
            "outcome": sim.outcome(agent, sim.feed_of(b.to_dict()), records[b["source_record_id"]]),
        })
    return rows


def needs_person(r, threshold, auto_limit):
    if not sim.needs_person(r["pred"], r["conf"], r["is_ca"], threshold):
        return False
    if auto_limit is None or r["is_ca"] or r["severity"] == "P0":
        return True
    controlled = ACTION_CATALOG[r["pred"]][2] == "CONTROLLED_ACTION"
    return not (controlled and r["exposure"] < auto_limit and r["conf"] >= AUTO_MIN_CONFIDENCE)


def evaluate_policy(rows, threshold, auto_limit):
    reviewed = auto = auto_value = reopened = silent = 0
    for r in rows:
        if needs_person(r, threshold, auto_limit):
            reviewed += 1
            continue
        if ACTION_CATALOG[r["pred"]][2] == "CONTROLLED_ACTION":
            auto += 1
            auto_value += r["exposure"]
        if r["outcome"] == "REOPENED":
            reopened += 1
        elif not r["correct"]:
            silent += 1
    n = len(rows)
    return {"reviewed_pct": round(100 * reviewed / n, 1), "controlled_auto": auto,
            "auto_value_cr": round(auto_value / 1e7, 2), "reopened": reopened, "silent_errors": silent}


def evaluate_reviewers(rows, threshold, miss_rate):
    """Expected outcome when a reviewer misses each wrong diagnosis with
    probability miss_rate (worked out exactly, not sampled)."""
    wrong = [r for r in rows if sim.needs_person(r["pred"], r["conf"], r["is_ca"], threshold) and not r["correct"]]
    closes = sum(r["outcome"] == "CLOSED" for r in wrong)
    return {"wrong_diagnoses_reviewed": len(wrong),
            "caught_by_person": round((1 - miss_rate) * len(wrong), 1),
            "caught_by_validation": round(miss_rate * (len(wrong) - closes), 1),
            "slipped_through": round(miss_rate * closes, 1)}


def main():
    frames, models, notice_text = load_frames(), R.load_models(), R.notices()
    threshold = models["production"]["threshold"]
    res = {"threshold": threshold, "auto_min_confidence": AUTO_MIN_CONFIDENCE}
    for label, (jitter, multi) in DATASETS.items():
        rows = break_rows(frames, models, notice_text, jitter, multi, seed=41)
        res[label] = {
            "policies": {name: evaluate_policy(rows, threshold, limit) for name, limit in POLICIES.items()},
            "reviewers": [dict(miss_rate=m, **evaluate_reviewers(rows, threshold, m)) for m in REVIEWER_MISS],
        }

    md = ["# Approval policy and reviewer error\n",
          "Written by `backend/eval/approval_policy.py` on the 607 test breaks. Messy = price and cash jitter "
          "0.005 plus a second fault on 20% of trades; very messy = jitter 0.01 and a second fault on 40%. "
          "Reviewer figures are expected counts. Risk-based rules only auto-run controlled actions that "
          f"are not P0, not corporate actions, and have calibrated confidence of at least {AUTO_MIN_CONFIDENCE}.\n"]
    for label in DATASETS:
        md.append(f"## Policies, {label} data\n")
        md.append("| policy | reviewed by a person | controlled fixes run without review | value of those (₹ crore) | reopened | silent errors |")
        md.append("|---|---|---|---|---|---|")
        for name, v in res[label]["policies"].items():
            md.append(f"| {name} | {v['reviewed_pct']}% | {v['controlled_auto']} | {v['auto_value_cr']} | "
                      f"{v['reopened']} | {v['silent_errors']} |")
        md.append(f"\n## Reviewers who miss mistakes, {label} data (strict policy)\n")
        md.append("| reviewer miss rate | wrong diagnoses reviewed | caught by the reviewer | caught by validation | slipped through |")
        md.append("|---|---|---|---|---|")
        for v in res[label]["reviewers"]:
            md.append(f"| {v['miss_rate']} | {v['wrong_diagnoses_reviewed']} | {v['caught_by_person']} | "
                      f"{v['caught_by_validation']} | {v['slipped_through']} |")
        md.append("")
    out = os.path.join(R.DOCS, "approval_policy")
    with open(out + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(out + ".json", "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)
    print("\n".join(md))


if __name__ == "__main__":
    main()
