"""
RCA Agent: why did this break happen?

Recommendation only. It never executes or authorises anything; it writes a
decision record (expected, actual, root cause, confidence, alternatives,
evidence) for a person, and for the Resolution Proposal agent, to act on.

How it decides:

1. The root-cause model (a Random Forest over 15 engineered features) gives a
   first diagnosis plus a probability for every class.
2. Document check. For corporate actions the numbers alone can't separate a
   mandatory event from a voluntary one: both show the custodian still
   holding the pre-event quantity. The MT564 notice can, through its CAMV
   field (MAND or VOLU). If the notice disagrees with the model, the notice
   wins and the record says so.
3. Escalation rules that are written down, not learned. Any corporate action
   goes to a person no matter how confident we are, and so does anything the
   model is less than 70% sure about. P0 only changes queue position.

An optional LLM step turns the record into a short paragraph for the analyst.
It needs OPENROUTER_API_KEY and is never used to make the decision.
"""

import os
import re
import sys

import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
MODEL_PATH = os.path.join(HERE, "..", "models", "ml_classifier", "saved", "root_cause_classifier.joblib")

sys.path.insert(0, HERE)
sys.path.insert(0, DATA_DIR)
from investigation import investigate, break_feed, gather_precedent_context  # noqa: E402
from features import build_features  # noqa: E402
from taxonomy import ROOT_CAUSES  # noqa: E402

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
    bundle = _model_bundle()
    model, le, cols = bundle["model"], bundle["label_encoder"], bundle["features"]

    row = _features_df().loc[break_id, cols].to_frame().T
    proba = model.predict_proba(row)[0]
    order = proba.argsort()[::-1][:top_k]
    ranked = [(le.classes_[i], float(proba[i])) for i in order]

    # A random forest often gives exactly 0 to most classes. Whatever sorts
    # second in that case is a tie-break, not a real second opinion, so only
    # keep alternatives the model actually voted for.
    alternatives = [(rc, p) for rc, p in ranked[1:] if p > 0.0]

    return {
        "predicted_root_cause": ranked[0][0],
        "confidence": round(ranked[0][1], 4),
        "alternatives": [{"root_cause": rc, "probability": round(p, 4)} for rc, p in alternatives],
    }


def read_ca_notice(text):
    """Pulls the fields we care about out of an MT564-style notice."""
    if not text:
        return None

    def field(tag):
        m = re.search(rf":{tag}//([^\s]+)", text)
        return m.group(1) if m else None

    mandatory_flag = field("22F::CAMV")
    if mandatory_flag not in ("MAND", "VOLU", "CHOS"):
        return None
    return {
        "event": field("22F::CAEV"),
        "mandatory_flag": mandatory_flag,
        "ratio": field("22F::CAON"),
        "effective_date": field("98A::EFFD"),
        "election_required": mandatory_flag != "MAND",
    }


def apply_document_check(classification, evidence):
    """Lets the CA notice settle mandatory vs voluntary."""
    if not evidence["corporate_action_context"]["is_corporate_action"]:
        return classification, None

    notice = read_ca_notice(evidence["document_evidence"].get("text"))
    if notice is None:
        return classification, None

    predicted = classification["predicted_root_cause"]
    corrected = predicted
    if notice["election_required"]:
        corrected = "CA_VOLUNTARY_DECISION"
    elif predicted == "CA_VOLUNTARY_DECISION":
        corrected = "CA_MANDATORY_NOT_REFLECTED"

    finding = dict(notice, model_said=predicted, changed=corrected != predicted)
    if corrected == predicted:
        return classification, finding

    probs = {predicted: classification["confidence"]}
    probs.update({a["root_cause"]: a["probability"] for a in classification["alternatives"]})
    updated = {
        "predicted_root_cause": corrected,
        # the model's own number would be misleading after a correction
        "confidence": classification["confidence"],
        "alternatives": [{"root_cause": rc, "probability": p}
                         for rc, p in probs.items() if rc != corrected],
    }
    return updated, finding


def expected_vs_actual(evidence):
    reported = evidence["reported"]
    return {"expected": reported["expected"], "actual": reported["observed"], "field": reported["field"]}


def decide_escalation(evidence, confidence):
    reasons = []
    if evidence["corporate_action_context"]["is_corporate_action"]:
        reasons.append("corporate action: a person always confirms the event and the entitlement, "
                       "whatever the model's confidence")
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        reasons.append(f"model confidence {confidence:.2f} is below {LOW_CONFIDENCE_THRESHOLD}")
    return {
        "requires_human_decision": bool(reasons),
        "reasons": reasons,
        "priority_flag": "P0 - move up the queue" if evidence["severity"] == "P0" else None,
    }


def cite_evidence(evidence, precedents):
    cites = [f"structured:{k}" for k, v in evidence["structured_evidence"].items() if v]
    doc = evidence["document_evidence"]
    if doc.get("has_document"):
        cites.append(f"document:{doc['doc_id']} ({doc['extraction_method']})")
        cites += [f"related_document:{r['break_id']}" for r in doc["related_documents"]]
    ca = evidence["corporate_action_context"]
    if ca["is_corporate_action"]:
        cites += [f"ca_reference:{r['action_type']}" for r in ca["reference_entries"]]
    cites += [f"precedent:{p['break_id']}" for p in precedents.get("precedents", [])]
    return cites


def explain(root_cause, ea, notice):
    description = ROOT_CAUSES[root_cause]["description"]
    text = f"{description}. Expected {ea['expected'] or 'a value'} on {ea['field']}, found {ea['actual'] or 'nothing'}."
    if notice:
        kind = "mandatory" if not notice["election_required"] else "voluntary"
        text += f" The MT564 notice marks this {notice['event'] or 'event'} as {kind}"
        if notice["ratio"]:
            text += f" (ratio {notice['ratio']})"
        text += "."
        if notice["changed"]:
            text += " The model read it differently, so the notice takes precedence."
    return text


def analyze(break_id, evidence=None):
    """RCA entry point. Reuses the Investigation bundle when the caller has one."""
    if evidence is None:
        evidence = investigate(break_id)

    classification = classify_root_cause(break_id)
    classification, notice = apply_document_check(classification, evidence)
    root_cause = classification["predicted_root_cause"]

    ea = expected_vs_actual(evidence)
    escalation = decide_escalation(evidence, classification["confidence"])
    precedents = gather_precedent_context(break_id, root_cause)
    evidence["precedent_context"] = precedents

    return {
        "break_id": break_id,
        "expected": ea["expected"],
        "actual": ea["actual"],
        "field": ea["field"],
        "root_cause": root_cause,
        "confidence": classification["confidence"],
        "alternative_explanations": classification["alternatives"],
        "document_finding": notice,
        "explanation": explain(root_cause, ea, notice),
        "precedents": precedents.get("precedents", []),
        "evidence_cited": cite_evidence(evidence, precedents),
        "requires_human_decision": escalation["requires_human_decision"],
        "escalation_reasons": escalation["reasons"],
        "priority_flag": escalation["priority_flag"],
    }


def synthesize_narrative(rca_result, evidence):
    """Optional: a 3 to 4 sentence write-up for the analyst. Needs OPENROUTER_API_KEY."""
    doc_text = evidence["document_evidence"].get("text") or ""
    ca_text = "\n".join(e["text"] for e in evidence["corporate_action_context"].get("reference_entries", []))
    prompt = (
        f"Break {rca_result['break_id']}: diagnosed root cause {rca_result['root_cause']} "
        f"(confidence {rca_result['confidence']:.2f}). Expected {rca_result['expected']}, "
        f"actual {rca_result['actual']} on {rca_result['field']}. "
        f"Alternatives: {rca_result['alternative_explanations']}.\n"
        f"Document: {doc_text[:800] or '(none)'}\n"
        f"Corporate action reference: {ca_text[:800] or '(none)'}\n\n"
        "Write a 3 to 4 sentence root-cause explanation for an operations analyst. "
        "Cite the evidence above. Do not recommend an action."
    )
    return llm.chat([{"role": "user", "content": prompt}], max_tokens=300)["content"]


if __name__ == "__main__":
    feats = _features_df()
    picks = list(feats.index[:3])
    picks.append(next(bid for bid in feats.index if break_feed(bid)["corporate_action_type"]))
    for bid in picks:
        r = analyze(bid)
        print(f"\n{bid}: {r['root_cause']} ({r['confidence']:.2f})")
        print(f"  {r['explanation']}")
        print(f"  needs a person: {r['requires_human_decision']} {r['escalation_reasons']}")
