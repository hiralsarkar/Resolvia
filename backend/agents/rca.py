"""
RCA Agent.

"Why did it happen?" Authority: Recommendation only (per the proposal's
Agent Architecture table) - this agent never executes or authorizes
anything, it produces a structured finding for a human (or, later, the
Resolution Proposal Agent) to act on.

Output shape (Expected / Actual / Evidence / Root Cause / Alternative
Explanation / Confidence) follows the "Agent Decision Record"
format used across the pipeline.

Two layers, same split as ingestion.py's deterministic-vs-LLM shape:
  1. Deterministic/ML core (fully real, no API key needed): expected-vs-
     actual pulled straight from the evidence bundle's structured
     records, root-cause classification from the already-trained model
     (backend/models/ml_classifier/saved/root_cause_classifier.joblib,
     TEST macro-F1 0.944), confidence + ranked alternatives from
     predict_proba.
  2. LLM narrative synthesis (same shape as ingestion.ingest_text - needs
     OPENROUTER_API_KEY set): weaves
     the structured finding + retrieved document/CA-reference text into
     a short evidence-grounded narrative. This is the one place an LLM
     genuinely earns its cost in this design (not
     every problem needs reasoning; explaining WHY across heterogeneous
     evidence does).

Governance rule, hardcoded not learned (project's core design
principle - "confidence should never determine authority"): any break
whose corporate_action_type is set ALWAYS gets requires_human_decision
= True, independent of model confidence. This is deliberately more
conservative than "only escalate if predicted voluntary" - the model
cannot reliably separate CA_MANDATORY_NOT_REFLECTED from
CA_VOLUNTARY_DECISION (see docs/model_comparison.md's confusion
matrix), so a confidence-gated escalation would be unsafe exactly where
it matters most. A human always sees CA cases; only the model's
alternatives inform what the human should look at first.
"""

import os
import sys
import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
MODEL_PATH = os.path.join(HERE, "..", "models", "ml_classifier", "saved", "root_cause_classifier.joblib")

sys.path.insert(0, HERE)
sys.path.insert(0, DATA_DIR)
from investigation import investigate, _tables  # noqa: E402
from check_ml_targets import build_features, FEATURE_COLS  # noqa: E402

sys.path.insert(0, os.path.join(HERE, ".."))
import llm  # noqa: E402

LOW_CONFIDENCE_THRESHOLD = 0.70

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


def classify_root_cause(break_id, top_k=3):
    """ML classification with ranked alternatives - the 'Confidence' and
    'Alternative Explanation' fields, straight from predict_proba, no
    LLM involved."""
    bundle = _model_bundle()
    model, le, feature_cols = bundle["model"], bundle["label_encoder"], bundle["features"]

    row = _features_df().loc[break_id, feature_cols].to_frame().T
    proba = model.predict_proba(row)[0]
    ranked_idx = proba.argsort()[::-1][:top_k]
    ranked = [(le.classes_[i], float(proba[i])) for i in ranked_idx]

    # A RandomForest often gives exact-0.0 probability to most classes
    # (unanimous tree voting) - when that happens, whatever's second in
    # sorted order is an arbitrary tie-break, not a real "second guess".
    # Only report alternatives that actually got model support.
    real_alternatives = [(rc, p) for rc, p in ranked[1:] if p > 0.0]

    return {
        "predicted_root_cause": ranked[0][0],
        "confidence": round(ranked[0][1], 4),
        "alternatives": [{"root_cause": rc, "probability": round(p, 4)} for rc, p in real_alternatives],
    }


def compute_expected_vs_actual(break_id):
    """Pulled directly from the break's own source_value/target_value/
    breaking_fields (set correctly per-root-cause by the generator) -
    NOT re-derived per family, since a fixed per-family field choice
    (e.g. always comparing settlement_date) silently shows identical
    expected/actual for a root cause that actually diverges on a
    different field (e.g. SETL_MISSING_INSTRUCTION diverges on
    instruction_status, not settlement_date) - caught this exact bug
    in testing before fixing it."""
    brk = _tables()["breaks"][break_id]
    return {"expected": brk["source_value"], "actual": brk["target_value"], "field": brk["breaking_fields"]}


def decide_escalation(evidence, classification):
    """Only CA-status and low confidence actually gate escalation -
    both are stated as `reasons`. P0 severity is reported separately as
    a priority flag: it changes queue order, not whether a human must
    decide the root cause, so it must never silently masquerade as an
    escalation reason in the output."""
    reasons = []
    if evidence["corporate_action_context"]["is_corporate_action"]:
        reasons.append("corporate action - mandatory/voluntary cannot be safely inferred from "
                        "structured data alone (see model_comparison.md confusion matrix); "
                        "always requires human judgment regardless of model confidence")
    if classification["confidence"] < LOW_CONFIDENCE_THRESHOLD:
        reasons.append(f"model confidence {classification['confidence']:.2f} below "
                        f"{LOW_CONFIDENCE_THRESHOLD} threshold")

    return {
        "requires_human_decision": bool(reasons),
        "reasons": reasons,
        "priority_flag": "P0 - expedite queue position" if evidence["severity"] == "P0" else None,
    }


def cite_evidence(evidence):
    cites = [f"structured:{k}" for k, v in evidence["structured_evidence"].items() if v]
    doc = evidence["document_evidence"]
    if doc.get("has_document"):
        cites.append(f"document:{doc['doc_id']} ({doc['extraction_method']})")
        cites += [f"related_document:{r['break_id']}" for r in doc["related_documents"]]
    ca = evidence["corporate_action_context"]
    if ca["is_corporate_action"]:
        cites += [f"ca_reference:{r['action_type']}" for r in ca["reference_entries"]]
    return cites


def analyze(break_id):
    """RCA Agent entry point. Chains off the Investigation Agent's
    evidence bundle - does not re-gather evidence itself."""
    evidence = investigate(break_id)
    classification = classify_root_cause(break_id)
    expected_actual = compute_expected_vs_actual(break_id)
    escalation = decide_escalation(evidence, classification)

    return {
        "break_id": break_id,
        "expected": expected_actual["expected"],
        "actual": expected_actual["actual"],
        "field": expected_actual["field"],
        "root_cause": classification["predicted_root_cause"],
        "confidence": classification["confidence"],
        "alternative_explanations": classification["alternatives"],
        "evidence_cited": cite_evidence(evidence),
        "requires_human_decision": escalation["requires_human_decision"],
        "escalation_reasons": escalation["reasons"],
        "priority_flag": escalation["priority_flag"],
    }


def synthesize_narrative(rca_result, evidence):
    """LLM narrative layer - same not-verified-live status as
    ingestion.ingest_text(); needs OPENROUTER_API_KEY set."""
    doc_text = evidence["document_evidence"].get("text", "")
    ca_text = "\n".join(e["text"] for e in evidence["corporate_action_context"].get("reference_entries", []))
    prompt = f"""Break {rca_result['break_id']}: predicted root cause {rca_result['root_cause']} \
(confidence {rca_result['confidence']:.2f}). Expected: {rca_result['expected']}. \
Actual: {rca_result['actual']}. Alternatives considered: {rca_result['alternative_explanations']}.
Supporting document: {doc_text[:800] or '(none)'}
Corporate action reference: {ca_text[:800] or '(none)'}

Write a 3-4 sentence root-cause explanation for an operations analyst, citing the specific \
evidence above. Do not recommend an action - that is a separate agent's job."""

    message = llm.chat([{"role": "user", "content": prompt}], max_tokens=300)
    return message["content"]


if __name__ == "__main__":
    breaks_features = _features_df()
    sample_ids = list(breaks_features.index[:3])
    # add one confirmed CA case for the escalation-rule demo
    for bid, b in _tables()["breaks"].items():
        if b["corporate_action_type"] and bid not in sample_ids:
            sample_ids.append(bid)
            break

    for bid in sample_ids:
        result = analyze(bid)
        print(f"\n=== {bid} ===")
        print(f"  predicted: {result['root_cause']} (confidence {result['confidence']:.2f})")
        print(f"  expected={result['expected']}  actual={result['actual']}")
        print(f"  alternatives: {result['alternative_explanations']}")
        print(f"  requires_human_decision={result['requires_human_decision']}  reasons={result['escalation_reasons']}")
        print(f"  evidence cited: {result['evidence_cited']}")
