"""
Investigation Agent.

"What happened?" - gathers structured records, documents and (where
relevant) corporate-action reference knowledge for one break, and
assembles it into an evidence bundle the RCA Agent (not yet built) will
reason over. By design this agent is READ/RETRIEVE
ONLY - it does not classify, judge, or recommend anything.

Structured evidence: trade/position/cash/settlement rows, read directly
(no model). Document evidence: only for breaks flagged
needs_evidence_bundle - OCR (EasyOCR, frozen) if the doc is a scanned
image, else the document text directly. RAG (two uses):
  - evidence retrieval: top-k documents semantically similar to the
    break's own evidence (surfaces related docs beyond the direct
    break_id join - e.g. another confirm mentioning the same
    counterparty/symbol).
  - knowledge grounding: for corporate-action breaks, top-k CA
    reference KB entries relevant to the break's context - this is
    what a later Judgment step needs BEFORE it can distinguish
    mandatory/voluntary; this agent only retrieves, never judges.

Historical-case precedent retrieval : a
resolved_cases corpus (backend/knowledge/build_resolved_cases.py) was
seeded by running a stratified sample of past breaks through the real
Orchestrator. gather_precedent_context() retrieves the top-k most
similar past resolutions - retrieval only, same as the CA reference
lookup; it surfaces what happened on similar cases before, it does not
recommend repeating it.
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
EMBEDDINGS_DIR = os.path.join(HERE, "..", "embeddings")
sys.path.insert(0, EMBEDDINGS_DIR)
from embed_store import EmbeddingStore  # noqa: E402

_TABLES = None
_EVIDENCE_INDEX = None
_CA_INDEX = None
_PRECEDENT_INDEX = None


def _load_csv(name):
    with open(os.path.join(DATA_DIR, name), newline="") as f:
        return list(csv.DictReader(f))


def _tables():
    global _TABLES
    if _TABLES is None:
        _TABLES = {
            "trades": {r["trade_id"]: r for r in _load_csv("trades.csv")},
            "positions": {r["trade_id"]: r for r in _load_csv("positions.csv")},
            "settlements": {r["trade_id"]: r for r in _load_csv("settlements.csv")},
            "cash": {},
            "breaks": {r["break_id"]: r for r in _load_csv("breaks.csv")},
        }
        cash_by_trade = {}
        for r in _load_csv("cash_transactions.csv"):
            cash_by_trade.setdefault(r["trade_id"], []).append(r)
        _TABLES["cash"] = cash_by_trade
    return _TABLES


def _evidence_index():
    global _EVIDENCE_INDEX
    if _EVIDENCE_INDEX is None:
        _EVIDENCE_INDEX = EmbeddingStore.load(os.path.join(EMBEDDINGS_DIR, "saved", "evidence_index"))
    return _EVIDENCE_INDEX


def _ca_index():
    global _CA_INDEX
    if _CA_INDEX is None:
        _CA_INDEX = EmbeddingStore.load(os.path.join(EMBEDDINGS_DIR, "saved", "ca_reference_index"))
    return _CA_INDEX


_PRECEDENT_INDEX_LOADED = False
_OCR_READER = None


def _precedent_index():
    global _PRECEDENT_INDEX, _PRECEDENT_INDEX_LOADED
    if not _PRECEDENT_INDEX_LOADED:
        path = os.path.join(EMBEDDINGS_DIR, "saved", "resolved_cases_index")
        _PRECEDENT_INDEX = EmbeddingStore.load(path) if os.path.exists(path + ".meta.json") else None
        _PRECEDENT_INDEX_LOADED = True
    return _PRECEDENT_INDEX


def gather_structured_evidence(trade_id):
    t = _tables()
    return {
        "trade": t["trades"].get(trade_id),
        "position": t["positions"].get(trade_id),
        "cash_transactions": t["cash"].get(trade_id, []),
        "settlement": t["settlements"].get(trade_id),
    }


def _read_document_text(doc_id):
    """Prefers the plain .txt (already-clean text). Only runs OCR if the
    document only exists as a scanned image - this mirrors how a real
    ingestion pipeline would pick the OCR path (scanned input only), not
    OCR everything indiscriminately."""
    txt_path = os.path.join(DATA_DIR, "broker_confirms", f"{doc_id}.txt")
    if os.path.exists(txt_path):
        with open(txt_path, encoding="utf-8") as f:
            return f.read(), "text"

    img_path = os.path.join(DATA_DIR, "scanned_images", f"{doc_id}.jpg")
    if os.path.exists(img_path):
        global _OCR_READER
        if _OCR_READER is None:
            import easyocr
            _OCR_READER = easyocr.Reader(["en"], gpu=False, verbose=False)
        lines = _OCR_READER.readtext(img_path, detail=0)
        return "\n".join(lines), "ocr"

    return None, None


def gather_document_evidence(break_row, top_k=3):
    if break_row["needs_evidence_bundle"] != "True":
        return {"has_document": False}

    mapping = _load_csv_cached("broker_confirms_mapping.csv")
    doc_row = next((m for m in mapping if m["break_id"] == break_row["break_id"]), None)
    if doc_row is None:
        return {"has_document": False}

    text, method = _read_document_text(doc_row["doc_id"])
    related = _evidence_index().query(text, top_k=top_k + 1) if text else []
    # drop the document's own match (top hit against itself)
    related = [(m, s) for m, s in related if m["break_id"] != break_row["break_id"]][:top_k]

    return {
        "has_document": True,
        "doc_id": doc_row["doc_id"],
        "extraction_method": method,
        "text": text,
        "related_documents": [{"break_id": m["break_id"], "root_cause": m["root_cause"],
                                "similarity": round(s, 3)} for m, s in related],
    }


def gather_ca_context(break_row, top_k=2):
    if not break_row.get("corporate_action_type"):
        return {"is_corporate_action": False}

    query = f"{break_row['root_cause']} {break_row['breaking_fields']}"
    hits = _ca_index().query(query, top_k=top_k)
    return {
        "is_corporate_action": True,
        "corporate_action_type": break_row["corporate_action_type"],
        "reference_entries": [{"action_type": m["action_type"], "classification": m["classification"],
                                "text": m["text"], "similarity": round(s, 3)} for m, s in hits],
    }


def gather_precedent_context(break_row, top_k=3):
    """Retrieval only, same authority boundary as gather_ca_context - this
    surfaces similar past resolutions, it does not recommend one."""
    index = _precedent_index()
    if index is None:
        return {"has_precedents": False}

    query = f"{break_row['root_cause']} {break_row['break_type']} {break_row['breaking_fields']}"
    hits = index.query(query, top_k=top_k + 1)
    hits = [(m, s) for m, s in hits if m["break_id"] != break_row["break_id"]][:top_k]
    return {
        "has_precedents": bool(hits),
        "precedents": [{"break_id": m["break_id"], "root_cause": m["root_cause"],
                         "recommended_action": m["recommended_action"],
                         "final_status": m["final_status"], "similarity": round(s, 3)}
                        for m, s in hits],
    }


_CSV_CACHE = {}


def _load_csv_cached(name):
    if name not in _CSV_CACHE:
        _CSV_CACHE[name] = _load_csv(name)
    return _CSV_CACHE[name]


def investigate(break_id):
    """The Investigation Agent's single entry point. Returns the full
    evidence bundle for one break - structured records, document
    evidence (if flagged), related-document retrieval, and CA reference
    grounding (if applicable). Read/retrieve only, per the authority
    table - no classification or judgment happens here."""
    breaks = _tables()["breaks"]
    if break_id not in breaks:
        raise KeyError(f"unknown break_id {break_id}")
    brk = breaks[break_id]
    trade_id = brk["source_record_id"]

    return {
        "break_id": break_id,
        "break_type": brk["break_type"],
        "root_cause": brk["root_cause"],
        "severity": brk["severity"],
        "structured_evidence": gather_structured_evidence(trade_id),
        "document_evidence": gather_document_evidence(brk),
        "corporate_action_context": gather_ca_context(brk),
        "precedent_context": gather_precedent_context(brk),
    }


if __name__ == "__main__":
    breaks = _tables()["breaks"]
    sample_ids = []
    # one evidence-bundle case per family, plus one CA case, for a quick smoke test
    for fam in ["POSITION", "CASH", "SETTLEMENT", "TRADE"]:
        for bid, b in breaks.items():
            if b["break_type"] == fam and b["needs_evidence_bundle"] == "True":
                sample_ids.append(bid)
                break
    for bid, b in breaks.items():
        if b["corporate_action_type"]:
            sample_ids.append(bid)
            break

    for bid in sample_ids:
        bundle = investigate(bid)
        doc = bundle["document_evidence"]
        ca = bundle["corporate_action_context"]
        print(f"\n=== {bid} ({bundle['root_cause']}, {bundle['break_type']}) ===")
        print(f"  document: {doc.get('has_document')} via {doc.get('extraction_method')}, "
              f"{len(doc.get('related_documents', []))} related docs found")
        if ca["is_corporate_action"]:
            top = ca["reference_entries"][0] if ca["reference_entries"] else None
            print(f"  CA ({ca['corporate_action_type']}): top reference = "
                  f"{top['action_type'] if top else None} ({top['classification'] if top else None})")
