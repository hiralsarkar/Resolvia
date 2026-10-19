"""
Stress tests: what happens to the models and the pipeline when the data gets
messy?

Everything is scored on the held-out TEST breaks. Two models are compared:
  clean       the tuned random forest from train.py, trained on clean data
  production  the noise-trained, calibrated model from build_production.py

Stressors (see data/perturb.py):
  jitter        noise on confirmed prices and cash amounts
  multi-cause   a second fault on some trades; a prediction counts as right
                if it names either fault
  scanned notice  OCR-style character errors in the corporate action notice
  missing notice  the notice never arrives, so only the model is left
  label noise   a share of training labels flipped before training

For each scenario it also replays the routing rules, so the report shows not
just accuracy but what reaches a person, what reopens, and what would slip
through unseen.

Run from backend/:  python eval/robustness.py
Writes docs/analysis/robustness.md and docs/analysis/robustness.json
"""

import csv
import json
import os
import re
import sys

import joblib
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

HERE = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(HERE, "..")
DATA_DIR = os.path.join(BACKEND, "..", "data")
DOCS = os.path.join(BACKEND, "..", "docs", "analysis")
for p in (DATA_DIR, BACKEND, HERE, os.path.join(BACKEND, "agents")):
    sys.path.insert(0, p)

from features import build_features, load_frames, FEATURE_COLS  # noqa: E402
from perturb import perturb, ocr_noise  # noqa: E402
from taxonomy import CA_ROOT_CAUSES  # noqa: E402
import rca  # noqa: E402
import sim  # noqa: E402

SAVED = os.path.join(BACKEND, "models", "ml_classifier", "saved")
JITTER = [0.0, 0.001, 0.0025, 0.005, 0.01]
MULTI = [0.0, 0.1, 0.2, 0.3, 0.4]
OCR_CER = [0.0, 0.05, 0.1, 0.2, 0.3]
MISSING = [0.0, 0.25, 0.5, 1.0]
LABEL_NOISE = [0.0, 0.05, 0.1, 0.2]


def load_models():
    clean = joblib.load(os.path.join(SAVED, "root_cause_classifier.joblib"))
    prod = joblib.load(os.path.join(SAVED, "root_cause_production.joblib"))
    return {"clean": clean, "production": prod}


def notices():
    by_break = {}
    with open(os.path.join(DATA_DIR, "broker_confirms_mapping.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["corporate_action_type"]:
                with open(os.path.join(DATA_DIR, "broker_confirms", f"{r['doc_id']}.txt"), encoding="utf-8") as d:
                    by_break[r["break_id"]] = d.read()
    return by_break


def exact_parser(text):
    """The original parser: the CAMV field, read exactly, or nothing."""
    m = re.search(r":22F::CAMV//(\S+)", text or "")
    if not m or m.group(1) not in ("MAND", "VOLU", "CHOS"):
        return None
    return {"election_required": m.group(1) != "MAND", "changed": False}


def is_ca(value):
    return isinstance(value, str) and value != ""


def predict(bundle, X):
    proba = bundle["model"].predict_proba(X)
    classes = bundle["label_encoder"].classes_
    return [classes[i] for i in proba.argmax(1)], proba.max(1), proba


def agent_view(pred, conf, ca_type, notice_text, parser=rca.read_ca_notice):
    """What the RCA agent ends up with once it has read the notice."""
    if not is_ca(ca_type) or not notice_text:
        return pred
    notice = parser(notice_text)
    if notice is None:
        return pred
    if notice["election_required"]:
        return "CA_VOLUNTARY_DECISION"
    return "CA_MANDATORY_NOT_REFLECTED" if pred == "CA_VOLUNTARY_DECISION" else pred


def score(truth_primary, truth_second, preds):
    """Macro-F1 where naming either fault of a two-fault break counts."""
    adjusted = [a if (b and p == b) else p for p, a, b in zip(preds, truth_primary, truth_second)]
    return round(float(f1_score(truth_primary, adjusted, average="macro")), 3)


def ece(conf, correct, bins=10):
    conf, correct = np.asarray(conf), np.asarray(correct, dtype=float)
    edges = np.linspace(0, 1, bins + 1)
    total = 0.0
    for lo, hi in zip(edges[:-1], edges[1:]):
        m = (conf > lo) & (conf <= hi) if lo > 0 else (conf >= lo) & (conf <= hi)
        if m.any():
            total += m.mean() * abs(conf[m].mean() - correct[m].mean())
    return round(float(total), 3)


def brier(proba, classes, truth):
    onehot = np.array([[c == t for c in classes] for t in truth], dtype=float)
    return round(float(np.mean(np.sum((proba - onehot) ** 2, axis=1))), 3)


def run_scenario(models, frames, notice_text, jitter=0.0, multi=0.0, cer=0.0, missing=0.0, seed=0):
    pf = perturb(frames, jitter=jitter, multi_cause=multi, split="TEST", seed=seed) if (jitter or multi) else \
        dict(frames, breaks=frames["breaks"].assign(second_cause=""))
    feats = build_features(pf).set_index("break_id")
    brk = pf["breaks"][pf["breaks"].split == "TEST"]
    X = feats.loc[brk.break_id, FEATURE_COLS]
    records = sim.records_by_trade(pf)
    rnd = np.random.default_rng(seed + 1)
    second = brk["second_cause"].fillna("").tolist()
    truth = brk["mismatch_type"].tolist()

    out = {}
    for name, bundle in models.items():
        preds, conf, _ = predict(bundle, X)
        agent = []
        for (_, b), p, c in zip(brk.iterrows(), preds, conf):
            text = notice_text.get(b["break_id"])
            if text and rnd.random() < missing:
                text = None
            if text and cer:
                text = ocr_noise(text, cer, seed=int(b["break_id"][3:]))
            agent.append(agent_view(p, c, b["corporate_action_type"], text))
        threshold = models["production"].get("threshold", 0.7)
        rows = []
        for (_, b), a, c, s in zip(brk.iterrows(), agent, conf, second):
            rows.append({"pred": a, "conf": float(c), "correct": a in (b["mismatch_type"], s),
                         "is_ca": is_ca(b["corporate_action_type"]),
                         "outcome_if_run": sim.outcome(a, sim.feed_of(b.to_dict()), records[b["source_record_id"]])})
        routing = sim.routing_cost(rows, threshold)
        correct = [r["correct"] for r in rows]
        out[name] = {
            "model_f1": score(truth, second, preds),
            "agent_f1": score(truth, second, agent),
            "accuracy": round(float(np.mean(correct)), 3),
            "ece": ece(conf, [p in (t, s) for p, t, s in zip(preds, truth, second)]),
            "reviewed": routing["reviews"], "reopened": routing["reopens"],
            "silent_errors": routing["silent_errors"], "n": len(rows),
        }
    return out


def notice_study(frames, models, notice_text):
    brk = frames["breaks"][(frames["breaks"].split == "TEST") & frames["breaks"].corporate_action_type.notna()]
    feats = build_features(frames).set_index("break_id")
    preds, conf, _ = predict(models["production"], feats.loc[brk.break_id, FEATURE_COLS])
    result = {"ocr": [], "missing": []}
    for cer in OCR_CER:
        row = {"cer": cer}
        for label, parser in (("exact", exact_parser), ("hardened", rca.read_ca_notice)):
            agent = [agent_view(p, c, b["corporate_action_type"],
                                ocr_noise(notice_text[b["break_id"]], cer, seed=int(b["break_id"][3:])), parser)
                     for (_, b), p, c in zip(brk.iterrows(), preds, conf)]
            row[label] = round(float(np.mean([a == t for a, t in zip(agent, brk.mismatch_type)])), 3)
        result["ocr"].append(row)
    for share in MISSING:
        rnd = np.random.default_rng(5)
        agent = [agent_view(p, c, b["corporate_action_type"],
                            None if rnd.random() < share else notice_text[b["break_id"]])
                 for (_, b), p, c in zip(brk.iterrows(), preds, conf)]
        result["missing"].append({"missing": share,
                                  "accuracy": round(float(np.mean([a == t for a, t in zip(agent, brk.mismatch_type)])), 3)})
    result["n"] = len(brk)
    return result


def label_noise_study(frames):
    feats = build_features(frames)
    train, test = feats[feats.split == "TRAIN"], feats[feats.split == "TEST"]
    classes = sorted(feats.root_cause.unique())
    rows = []
    for rate in LABEL_NOISE:
        rnd = np.random.default_rng(11)
        y = train.root_cause.to_numpy().copy()
        flip = rnd.random(len(y)) < rate
        y[flip] = [rnd.choice([c for c in classes if c != v]) for v in y[flip]]
        rf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1).fit(train[FEATURE_COLS], y)
        rows.append({"label_noise": rate,
                     "macro_f1": round(float(f1_score(test.root_cause, rf.predict(test[FEATURE_COLS]), average="macro")), 3)})
    return rows


def calibration_study(frames, models):
    feats = build_features(frames).set_index("break_id")
    out = {}
    for label, (jitter, multi) in {"clean": (0, 0), "messy": (0.005, 0.2)}.items():
        pf = perturb(frames, jitter=jitter, multi_cause=multi, split="TEST", seed=31) if jitter else frames
        f = build_features(pf).set_index("break_id") if jitter else feats
        test = f[f.split == "TEST"]
        out[label] = {}
        for name, bundle in models.items():
            preds, conf, proba = predict(bundle, test[FEATURE_COLS])
            out[label][name] = {"ece": ece(conf, [p == t for p, t in zip(preds, test.root_cause)]),
                                "brier": brier(proba, bundle["label_encoder"].classes_, test.root_cause),
                                "share_at_0_or_1": round(float(np.mean((conf < 0.01) | (conf > 0.99))), 3)}
    return out


def write_report(res):
    def table(header, rows):
        lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
        lines += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
        return "\n".join(lines)

    md = ["# Robustness report\n",
          "Written by `backend/eval/robustness.py`. All numbers are on the 607 held-out test breaks. "
          "`clean` is the tuned random forest trained on clean data; `production` is the noise-trained, "
          "calibrated model the RCA agent uses. Agent F1 includes reading the corporate action notice. "
          "Reviewed, reopened and silent errors replay the routing rules with the production threshold "
          f"({res['threshold']}).\n"]
    for key, title, col in (("jitter", "Price and cash jitter", "jitter"),
                            ("multi", "Second fault on the same trade", "share")):
        md.append(f"## {title}\n")
        md.append(table([col, "model F1 clean / prod", "agent F1 clean / prod", "reviewed", "reopened", "silent errors"],
                        [[r["level"], f"{r['clean']['model_f1']} / {r['production']['model_f1']}",
                          f"{r['clean']['agent_f1']} / {r['production']['agent_f1']}",
                          r["production"]["reviewed"], r["production"]["reopened"],
                          r["production"]["silent_errors"]] for r in res[key]]) + "\n")
    m = res["messy"]
    md.append("## Everything at once\n\nJitter 0.005, a second fault on 20% of trades, notices scanned at a "
              "5% character error rate and 25% of them missing.\n")
    md.append(table(["model", "model F1", "agent F1", "reviewed", "reopened", "silent errors"],
                    [[k, v["model_f1"], v["agent_f1"], v["reviewed"], v["reopened"], v["silent_errors"]]
                     for k, v in m.items()]) + "\n")
    n = res["notices"]
    md.append(f"## Corporate action notices ({n['n']} test corporate actions)\n\nAccuracy on the corporate-action "
              "breaks only, as the notice gets harder to read.\n")
    md.append(table(["character error rate", "exact parser", "hardened parser"],
                    [[r["cer"], r["exact"], r["hardened"]] for r in n["ocr"]]) + "\n")
    md.append(table(["share of notices missing", "accuracy"], [[r["missing"], r["accuracy"]] for r in n["missing"]]) + "\n")
    md.append("## Label noise in training\n")
    md.append(table(["labels flipped", "test macro-F1"], [[r["label_noise"], r["macro_f1"]] for r in res["label_noise"]]) + "\n")
    md.append("## Calibration\n\nExpected calibration error (lower is better), Brier score, and the share of "
              "predictions with confidence exactly 0 or 1.\n")
    rows = [[d, name, v["ece"], v["brier"], v["share_at_0_or_1"]]
            for d, models in res["calibration"].items() for name, v in models.items()]
    md.append(table(["data", "model", "ECE", "Brier", "share at 0 or 1"], rows) + "\n")
    with open(os.path.join(DOCS, "robustness.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(os.path.join(DOCS, "robustness.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=2)


def main():
    frames = load_frames()
    models = load_models()
    notice_text = notices()
    res = {"threshold": models["production"]["threshold"], "jitter": [], "multi": []}
    for level in JITTER:
        print(f"jitter {level}")
        res["jitter"].append(dict(level=level, **run_scenario(models, frames, notice_text, jitter=level, seed=1)))
    for level in MULTI:
        print(f"multi-cause {level}")
        res["multi"].append(dict(level=level, **run_scenario(models, frames, notice_text, multi=level, seed=2)))
    print("everything at once")
    res["messy"] = run_scenario(models, frames, notice_text, jitter=0.005, multi=0.2, cer=0.05, missing=0.25, seed=3)
    print("notices, label noise, calibration")
    res["notices"] = notice_study(frames, models, notice_text)
    res["label_noise"] = label_noise_study(frames)
    res["calibration"] = calibration_study(frames, models)
    write_report(res)
    print(open(os.path.join(DOCS, "robustness.md")).read())


if __name__ == "__main__":
    main()
