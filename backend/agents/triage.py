"""
Triage Agent: what is this break and where should it go?

No financial authority. It checks, classifies and routes, and that's all.

  validate_break     plain data checks: the trade, position and settlement
                     records exist and the break is still OPEN. If they fail
                     the case stops here.
  classify_family    the family model (Random Forest, 4 classes). Family is
                     easy to separate, which is exactly what you want from a
                     routing step: fast and nearly always right. The harder
                     root-cause call is left to RCA.
  family agreement   compares the model's family with the family the
                     reconciliation engine already tagged. If they disagree we
                     show it rather than quietly picking one; it usually means
                     bad reference data or a break that spans two families.
  priority, route    URGENT for P0 or exposure of 10 lakh and up (the same
                     rule Resolution uses for HIGH risk, so the two never
                     disagree), then the desk for the family. Corporate
                     actions always go to the CA specialists.
"""

import os
import sys

import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
MODEL_PATH = os.path.join(HERE, "..", "models", "family_classifier", "saved", "family_classifier.joblib")

sys.path.insert(0, HERE)
sys.path.insert(0, DATA_DIR)
from investigation import _tables, break_feed  # noqa: E402
from features import build_features  # noqa: E402

HIGH_EXPOSURE_THRESHOLD = 1_000_000  # INR, same as resolution.py

DESK_BY_FAMILY = {
    "POSITION": "Position/Custody Desk",
    "CASH": "Cash Management Desk",
    "SETTLEMENT": "Settlements Desk",
    "TRADE": "Trade Support Desk",
}

_MODEL_BUNDLE = None
_FEATURES_DF = None


def _model_bundle():
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is None:
        _MODEL_BUNDLE = joblib.load(MODEL_PATH)
    return _MODEL_BUNDLE


def _features_df():
    global _FEATURES_DF
    if _FEATURES_DF is None:
        _FEATURES_DF = build_features().set_index("break_id")
    return _FEATURES_DF


def validate_break(break_id):
    t = _tables()
    if break_id not in t["breaks"]:
        return {"valid": False, "issues": [f"break_id {break_id} not found"]}
    feed = break_feed(break_id)
    trade_id = feed["source_record_id"]

    issues = []
    if trade_id not in t["trades"]:
        issues.append(f"trade {trade_id} has no trades.csv record")
    if trade_id not in t["positions"]:
        issues.append(f"trade {trade_id} has no positions.csv record")
    if trade_id not in t["settlements"]:
        issues.append(f"trade {trade_id} has no settlements.csv record")
    if feed["status"] != "OPEN":
        issues.append(f"break status is {feed['status']!r}, not OPEN, so it may already be handled")
    return {"valid": not issues, "issues": issues}


def classify_family(break_id):
    bundle = _model_bundle()
    model, le, cols = bundle["model"], bundle["label_encoder"], bundle["features"]
    row = _features_df().loc[break_id, cols].to_frame().T
    proba = model.predict_proba(row)[0]
    top = proba.argmax()
    return {"predicted_family": le.classes_[top], "confidence": round(float(proba[top]), 4)}


def check_family_agreement(feed, predicted_family):
    return {
        "upstream_family": feed["break_type"],
        "model_family": predicted_family,
        "agrees": feed["break_type"] == predicted_family,
    }


def determine_priority(feed):
    trade = _tables()["trades"].get(feed["source_record_id"])
    exposure = float(trade["trade_value"]) if trade and trade.get("trade_value") else 0.0
    if feed["severity"] == "P0" or exposure >= HIGH_EXPOSURE_THRESHOLD:
        priority = "URGENT"
    elif feed["severity"] == "P1":
        priority = "HIGH"
    else:
        priority = "STANDARD"
    return {"priority": priority, "financial_exposure": exposure}


def determine_route(feed, family):
    if feed.get("corporate_action_type"):
        return "Corporate Actions specialist queue"
    return DESK_BY_FAMILY.get(family, "General Operations Queue")


def triage(break_id):
    check = validate_break(break_id)
    feed = break_feed(break_id)
    family = classify_family(break_id)
    priority = determine_priority(feed)

    return {
        "break_id": break_id,
        "valid": check["valid"],
        "validation_issues": check["issues"],
        "predicted_family": family["predicted_family"],
        "family_confidence": family["confidence"],
        "family_agreement": check_family_agreement(feed, family["predicted_family"]),
        "priority": priority["priority"],
        "financial_exposure": priority["financial_exposure"],
        "route": determine_route(feed, family["predicted_family"]),
    }


if __name__ == "__main__":
    breaks = _tables()["breaks"]
    agree = sum(triage(b)["family_agreement"]["agrees"] for b in breaks)
    print(f"model family agrees with the upstream tag on {agree}/{len(breaks)} breaks")
