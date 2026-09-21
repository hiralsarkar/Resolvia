"""
Triage Agent.

"What is this break and where should it go?" Authority: "No financial
execution" per the proposal's Agent Architecture table - this agent
validates, classifies, and routes; it never proposes or approves an
action. First step in the pipeline, before Investigation even runs.

Four pieces:
  - validate_break(): deterministic sanity checks on the raw break
    record (trade exists, has structured evidence, not already closed).
    No model, no LLM - this is a data-quality gate, not a judgment call.
  - classify_family(): the family classifier (backend/models/
    family_classifier) - fast, near-certain routing signal (1.000 TEST
    accuracy - appropriate HERE, see that module's docstring for why
    this isn't the same degenerate-target problem the RCA target had).
  - check_family_agreement(): compares the model's independent
    classification against the family the upstream reconciliation
    system already tagged the break with (breaks.csv's own
    `break_type`, which a real reconciliation engine would supply at
    break-creation time - RESOLVIA doesn't replace that). A disagreement
    is itself a signal worth surfacing (bad reference data, a break
    that genuinely straddles two families), not something to silently
    paper over by trusting one side blindly.
  - determine_priority() / determine_route(): deterministic. Priority
    reuses the same severity+exposure logic as resolution.py's risk
    assessment (kept consistent on purpose - a break shouldn't be
    "LOW risk" at Resolution but "URGENT priority" at Triage for the
    same underlying reasons). Route is desk assignment by family, with
    corporate-action breaks always routed to the CA specialist queue
    regardless of family, since CA is one specialist
    scenario among the families.
"""

import os
import sys
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
MODEL_PATH = os.path.join(HERE, "..", "models", "family_classifier", "saved", "family_classifier.joblib")

sys.path.insert(0, HERE)
sys.path.insert(0, DATA_DIR)
from investigation import _tables  # noqa: E402
from check_ml_targets import build_features  # noqa: E402

HIGH_EXPOSURE_THRESHOLD = 1_000_000  # INR - same threshold as resolution.py, deliberately

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
    """No model - a break either has the structured evidence a
    reconciliation break should have, or it doesn't."""
    t = _tables()
    brk = t["breaks"].get(break_id)
    if brk is None:
        return {"valid": False, "issues": [f"break_id {break_id} not found"]}

    trade_id = brk["source_record_id"]
    issues = []
    if trade_id not in t["trades"]:
        issues.append(f"referenced trade_id {trade_id} has no trades.csv record")
    if trade_id not in t["positions"]:
        issues.append(f"trade_id {trade_id} has no positions.csv record")
    if trade_id not in t["settlements"]:
        issues.append(f"trade_id {trade_id} has no settlements.csv record")
    if brk["status"] not in ("OPEN",):
        issues.append(f"break status is {brk['status']!r}, not OPEN - may already be handled")

    return {"valid": len(issues) == 0, "issues": issues}


def classify_family(break_id):
    bundle = _model_bundle()
    model, le, feature_cols = bundle["model"], bundle["label_encoder"], bundle["features"]
    row = _features_df().loc[break_id, feature_cols].to_frame().T
    proba = model.predict_proba(row)[0]
    top = proba.argmax()
    return {"predicted_family": le.classes_[top], "confidence": round(float(proba[top]), 4)}


def check_family_agreement(break_id, predicted_family):
    upstream_family = _tables()["breaks"][break_id]["break_type"]
    return {
        "upstream_family": upstream_family,
        "model_family": predicted_family,
        "agrees": upstream_family == predicted_family,
    }


def determine_priority(brk):
    trade = _tables()["trades"].get(brk["source_record_id"])
    exposure = float(trade["trade_value"]) if trade and trade.get("trade_value") else 0.0
    if brk["severity"] == "P0" or exposure >= HIGH_EXPOSURE_THRESHOLD:
        return {"priority": "URGENT", "financial_exposure": exposure}
    if brk["severity"] == "P1":
        return {"priority": "HIGH", "financial_exposure": exposure}
    return {"priority": "STANDARD", "financial_exposure": exposure}


def determine_route(brk, family):
    if brk.get("corporate_action_type"):
        return "Corporate Actions specialist queue"
    return DESK_BY_FAMILY.get(family, "General Operations Queue")


def triage(break_id):
    """Triage Agent entry point. First step of the pipeline - does not
    call Investigation/RCA, they run after this."""
    validation = validate_break(break_id)
    brk = _tables()["breaks"][break_id]

    classification = classify_family(break_id)
    agreement = check_family_agreement(break_id, classification["predicted_family"])
    priority = determine_priority(brk)
    route = determine_route(brk, classification["predicted_family"])

    return {
        "break_id": break_id,
        "valid": validation["valid"],
        "validation_issues": validation["issues"],
        "predicted_family": classification["predicted_family"],
        "family_confidence": classification["confidence"],
        "family_agreement": agreement,
        "priority": priority["priority"],
        "financial_exposure": priority["financial_exposure"],
        "route": route,
    }


if __name__ == "__main__":
    breaks = _tables()["breaks"]
    seen_families = set()
    sample_ids = []
    for bid, b in breaks.items():
        if b["break_type"] not in seen_families:
            seen_families.add(b["break_type"])
            sample_ids.append(bid)
    for bid, b in breaks.items():
        if b["corporate_action_type"] and bid not in sample_ids:
            sample_ids.append(bid)
            break

    disagreements = 0
    for bid in sample_ids:
        result = triage(bid)
        print(f"\n=== {bid} ===")
        print(f"  valid={result['valid']}  predicted_family={result['predicted_family']} "
              f"(conf {result['family_confidence']:.2f})  agrees_with_upstream="
              f"{result['family_agreement']['agrees']}")
        print(f"  priority={result['priority']}  exposure={result['financial_exposure']:,.0f}  "
              f"route={result['route']}")

    # full-dataset agreement check
    agree_count = 0
    for bid in breaks:
        r = triage(bid)
        if r["family_agreement"]["agrees"]:
            agree_count += 1
        else:
            disagreements += 1
    print(f"\nFull dataset: {agree_count}/{len(breaks)} model predictions agree with "
          f"upstream break_type ({disagreements} disagreements)")
