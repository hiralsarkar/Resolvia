"""
RCA Agent: why did this break happen?

Recommendation only. It never executes or authorises anything; it writes a
decision record (expected, actual, root cause, confidence, alternatives,
evidence) for a person, and for the Resolution Proposal agent, to act on.

How it decides:

1. The root-cause model gives a first diagnosis plus a probability for every
   class. It's a random forest over 15 engineered features, trained on clean
   and purposely messy copies of the data and then calibrated, so its
   confidence behaves like a probability (see build_production.py).
2. Document check. For corporate actions the numbers alone can't separate a
   mandatory event from a voluntary one: both show the custodian still
   holding the pre-event quantity. The MT564 notice can. I read three signals
   from it (the CAMV field, the event code and the narrative), each tolerant
   of a small OCR slip. If they agree and disagree with the model, the notice
   wins and the record says so.
3. Escalation rules that are written down, not learned. Any corporate action
   goes to a person no matter how confident the model is, and so does any
   diagnosis below the confidence threshold. The threshold was chosen by
   replaying the routing rules at different cut-offs and keeping the cheapest.
   P0 only changes queue position.

An optional LLM step turns the record into a short paragraph for the analyst.
It needs OPENROUTER_API_KEY and is never used to make the decision.
"""

import os
import re
import sys
from decimal import Decimal, InvalidOperation

import joblib

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
SAVED_DIR = os.path.join(HERE, "..", "models", "ml_classifier", "saved")
# the noise-trained, calibrated model if it has been built, else the plain tuned one
MODEL_PATH = next(p for p in (os.path.join(SAVED_DIR, "root_cause_production.joblib"),
                              os.path.join(SAVED_DIR, "root_cause_classifier.joblib")) if os.path.exists(p))

sys.path.insert(0, HERE)
sys.path.insert(0, DATA_DIR)
from investigation import investigate, break_feed, gather_precedent_context  # noqa: E402
from features import build_features  # noqa: E402
from taxonomy import ROOT_CAUSES  # noqa: E402

sys.path.insert(0, os.path.join(HERE, ".."))
import store  # noqa: E402
import llm  # noqa: E402

# Fallback only. The production model carries its own threshold, chosen by
# cost in build_production.py.
DEFAULT_THRESHOLD = 0.70

_MODEL_BUNDLE = None
_FEATURES_DF = None


def _model_bundle():
    global _MODEL_BUNDLE
    if _MODEL_BUNDLE is None:
        _MODEL_BUNDLE = joblib.load(MODEL_PATH)
    return _MODEL_BUNDLE


def confidence_threshold():
    return _model_bundle().get("threshold", DEFAULT_THRESHOLD)


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


# OCR tends to read letters as look-alike digits. Mapping them back before
# matching lets a slightly damaged scan still be read.
_DIGIT_TO_LETTER = str.maketrans({"0": "O", "1": "I", "5": "S", "8": "B", "4": "A"})

MANDATORY_EVENTS = {"BONU", "SPLF", "SPLR", "DVSE", "CAPG"}
VOLUNTARY_EVENTS = {"TEND", "EXOF", "BIDS", "CONV", "RHTS"}
FLAGS = ("MAND", "VOLU", "CHOS")


def _closest(token, choices, max_distance=1):
    """The choice within max_distance substitutions of token, if exactly one is."""
    if not token or len(token) < 4:
        return None
    token = token[:4]
    near = [c for c in choices if sum(a != b for a, b in zip(token, c)) <= max_distance]
    return near[0] if len(near) == 1 else None


def notice_signals(text):
    """Every signal the notice gives on mandatory vs voluntary, with the field it
    came from and the value read, so the analyst can see what drove the call.
    Each entry: {"signal", "field", "read", "points_to"} with points_to MAND or VOLU."""
    if not text:
        return []
    norm = text.upper().translate(_DIGIT_TO_LETTER)
    out = []
    m = re.search(r"::CA[MN]V//(\S{4})", norm)
    flag = _closest(m.group(1), FLAGS) if m else None
    if flag:
        out.append({"signal": "CAMV field", "field": ":22F::CAMV", "read": flag,
                    "points_to": "MAND" if flag == "MAND" else "VOLU"})
    m = re.search(r"::CA[EF]V//(\S{4})", norm)
    event = _closest(m.group(1), MANDATORY_EVENTS | VOLUNTARY_EVENTS) if m else None
    if event:
        out.append({"signal": "event code", "field": ":22F::CAEV", "read": event,
                    "points_to": "MAND" if event in MANDATORY_EVENTS else "VOLU"})
    for phrase, verdict in (("NO ELECTION", "MAND"), ("MECHANICAL EVENT", "MAND"),
                            ("ELECTION REQUIRED", "VOLU"), ("NOAC", "VOLU")):
        if phrase in norm:
            out.append({"signal": "narrative", "field": "narrative text", "read": phrase, "points_to": verdict})
            break
    return out


def notice_verdict(signals):
    """agreed (all readable signals point one way), conflict, or unreadable."""
    votes = {s["points_to"] for s in signals}
    return "unreadable" if not votes else ("agreed" if len(votes) == 1 else "conflict")


def read_ca_notice(text):
    """Reads an MT564-style notice and decides whether it needs an election.
    Three independent signals, from most to least direct:
      1. the CAMV field (MAND, VOLU or CHOS)
      2. the event code in CAEV (a bonus is mandatory, a tender voluntary)
      3. the narrative ("NO ELECTION REQUIRED", "ELECTION REQUIRED", NOAC)
    Each one tolerates a single OCR slip. If they disagree, or none can be
    read, it returns None and the break falls back to the model and a person."""
    if not text:
        return None
    def raw_field(tag):
        m = re.search(rf":{tag}//([^\s]+)", text)
        return m.group(1) if m else None
    detail = notice_signals(text)
    if notice_verdict(detail) != "agreed":
        return None
    decided = detail[0]["points_to"]
    event = next((d["read"] for d in detail if d["signal"] == "event code"), None)
    return {
        "event": event or raw_field("22F::CAEV"),
        "mandatory_flag": decided,
        "ratio": raw_field("22F::CAON"),
        "effective_date": raw_field("98A::EFFD"),
        "election_required": decided != "MAND",
        "signals": [d["signal"] for d in detail],
        "signal_detail": detail,
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
    threshold = confidence_threshold()
    if confidence < threshold:
        reasons.append(f"model confidence {confidence:.2f} is below {threshold:.2f}")
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


def entitlement_calculation(evidence, notice):
    """Return an auditable quantity calculation when a notice has a ratio."""
    if not notice or not notice.get("ratio"):
        return None
    match = re.match(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*:\s*([0-9]+(?:\.[0-9]+)?)\s*$", notice["ratio"])
    if not match:
        return {"ratio": {"held": None, "new": None, "resulting_multiplier": None},
                "rounding_rule": "not stated", "status": "UNPARSED"}
    held, new = (Decimal(x) for x in match.groups())
    if held == 0:
        return {"ratio": {"held": str(held), "new": str(new), "resulting_multiplier": None},
                "rounding_rule": "not stated", "status": "INVALID"}
    position = evidence.get("structured_evidence", {}).get("position") or {}
    observed = evidence.get("reported", {}).get("actual")
    try:
        source_quantity = Decimal(str(position.get("expected_quantity")))
        observed_quantity = Decimal(str(observed))
    except (InvalidOperation, TypeError):
        return {"ratio": {"held": str(held), "new": str(new), "resulting_multiplier": str(new / held)},
                "rounding_rule": "not stated", "status": "NO_QUANTITY"}
    multiplier = new / held
    expected = source_quantity * multiplier
    return {
        "ratio": {"held": str(held), "new": str(new), "resulting_multiplier": str(multiplier)},
        "source_quantity": str(source_quantity), "expected_quantity": str(expected),
        "observed_quantity": str(observed_quantity), "delta": str(expected - observed_quantity),
        "rounding_rule": "not stated", "status": "CALCULATED",
    }


def analyze(break_id, evidence=None):
    """RCA entry point. Reuses the Investigation bundle when the caller has one."""
    if evidence is None:
        evidence = investigate(break_id)

    classification = classify_root_cause(break_id)
    classification, notice = apply_document_check(classification, evidence)
    is_ca = evidence["corporate_action_context"]["is_corporate_action"]
    signals = notice_signals(evidence["document_evidence"].get("text")) if is_ca else []
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
        "notice_signals": signals,
        "notice_verdict": notice_verdict(signals) if is_ca else None,
        "notice_signals_captured_at": store.now() if is_ca else None,
        "entitlement_calculation": entitlement_calculation(evidence, notice),
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
