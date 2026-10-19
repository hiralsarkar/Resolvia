"""
Investigation Agent: what evidence do we have for this break?

This agent only reads and retrieves. It never classifies or recommends.
Everything it returns comes from what a real operations team would actually
have when a break lands: the break feed from the reconciliation engine, the
trade, position, cash and settlement records, any document attached to the
trade, and our own knowledge bases.

It never looks at the root-cause label in breaks.csv. That
column is the ground truth we generated, and a live reconciliation engine
would not know the root cause. Using it here would make the retrieval look
far better than it really is.

What it gathers:
  structured records   trade, position, cash rows, settlement (straight lookups)
  document             the .txt for the trade if there is one, otherwise OCR
                       on the scanned image
  related documents    top-k documents that read like this one
  corporate actions    for CA breaks, the most relevant entries from the CA
                       reference knowledge base, searched with the notice text

Precedent retrieval (similar resolved cases) lives here too, but it is called
by the RCA agent once it has a diagnosis, because "what did we do last time"
only makes sense once you know what kind of break it is.
"""

import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
EMBEDDINGS_DIR = os.path.join(HERE, "..", "embeddings")
sys.path.insert(0, EMBEDDINGS_DIR)
sys.path.insert(0, DATA_DIR)
from embed_store import EmbeddingStore  # noqa: E402
from taxonomy import ROOT_CAUSES  # noqa: E402

_TABLES = None
_CSV_CACHE = {}
_INDEXES = {}
_OCR_READER = None

# Columns of breaks.csv that only the data generator knows. Nothing in the
# live pipeline should read these.
GROUND_TRUTH_COLUMNS = ("mismatch_type", "root_cause")


def _load_csv(name):
    with open(os.path.join(DATA_DIR, name), newline="") as f:
        return list(csv.DictReader(f))


def _load_csv_cached(name):
    if name not in _CSV_CACHE:
        _CSV_CACHE[name] = _load_csv(name)
    return _CSV_CACHE[name]


def _tables():
    global _TABLES
    if _TABLES is None:
        cash_by_trade = {}
        for r in _load_csv("cash_transactions.csv"):
            cash_by_trade.setdefault(r["trade_id"], []).append(r)
        _TABLES = {
            "trades": {r["trade_id"]: r for r in _load_csv("trades.csv")},
            "positions": {r["trade_id"]: r for r in _load_csv("positions.csv")},
            "settlements": {r["trade_id"]: r for r in _load_csv("settlements.csv")},
            "cash": cash_by_trade,
            "breaks": {r["break_id"]: r for r in _load_csv("breaks.csv")},
        }
    return _TABLES


def break_feed(break_id):
    """The break as the reconciliation engine reports it, without the labels."""
    row = _tables()["breaks"][break_id]
    return {k: v for k, v in row.items() if k not in GROUND_TRUTH_COLUMNS}


def _index(name):
    """Loads a saved embedding index once. Returns None if it hasn't been built."""
    if name not in _INDEXES:
        path = os.path.join(EMBEDDINGS_DIR, "saved", name)
        _INDEXES[name] = EmbeddingStore.load(path) if os.path.exists(path + ".meta.json") else None
    return _INDEXES[name]


def gather_structured_evidence(trade_id):
    t = _tables()
    return {
        "trade": t["trades"].get(trade_id),
        "position": t["positions"].get(trade_id),
        "cash_transactions": t["cash"].get(trade_id, []),
        "settlement": t["settlements"].get(trade_id),
    }


def _read_document_text(doc_id):
    """Use the clean text if we have it and only OCR when all we have is a scan,
    which is how an ingestion pipeline would normally behave."""
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


def _document_for(break_id):
    mapping = _load_csv_cached("broker_confirms_mapping.csv")
    return next((m for m in mapping if m["break_id"] == break_id), None)


def gather_document_evidence(feed, top_k=3):
    if feed["needs_evidence_bundle"] != "True":
        return {"has_document": False}

    doc_row = _document_for(feed["break_id"])
    if doc_row is None:
        return {"has_document": False}

    text, method = _read_document_text(doc_row["doc_id"])
    related = []
    index = _index("evidence_index")
    if text and index is not None:
        hits = index.query(text, top_k=top_k + 1)
        # the best hit is usually the document itself
        hits = [(m, s) for m, s in hits if m["break_id"] != feed["break_id"]][:top_k]
        related = [{"break_id": m["break_id"], "doc_id": m["doc_id"], "similarity": round(s, 3)}
                   for m, s in hits]

    return {
        "has_document": True,
        "doc_id": doc_row["doc_id"],
        "extraction_method": method,
        "text": text,
        "related_documents": related,
    }


def gather_ca_context(feed, document, top_k=2):
    """For a corporate-action break, look up the CA definitions that match.

    We search with the notice itself when we have it (an MT564 carries the event
    type and whether it is mandatory), otherwise with what the break feed says."""
    if not feed.get("corporate_action_type"):
        return {"is_corporate_action": False}

    if document.get("has_document") and document.get("text"):
        query = document["text"]
    else:
        query = f"{feed['corporate_action_type']} corporate action, {feed['breaking_fields']} differs"

    index = _index("ca_reference_index")
    hits = index.query(query, top_k=top_k) if index is not None else []
    return {
        "is_corporate_action": True,
        "corporate_action_type": feed["corporate_action_type"],
        "reference_entries": [{"action_type": m["action_type"], "classification": m["classification"],
                               "text": m["text"], "similarity": round(s, 3)} for m, s in hits],
    }


def gather_precedent_context(break_id, root_cause, top_k=3):
    """Similar cases we have already worked, for a given (diagnosed) root cause.

    Retrieval only: it shows what happened before, it does not decide anything."""
    index = _index("resolved_cases_index")
    if index is None:
        return {"has_precedents": False, "precedents": []}

    feed = break_feed(break_id)
    description = ROOT_CAUSES.get(root_cause, {}).get("description", root_cause)
    query = f"{description} | {feed['break_type']} | {feed['breaking_fields']}"
    hits = index.query(query, top_k=top_k + 1)
    hits = [(m, s) for m, s in hits if m["break_id"] != break_id][:top_k]
    return {
        "has_precedents": bool(hits),
        "precedents": [{"break_id": m["break_id"], "root_cause": m["root_cause"],
                        "recommended_action": m["recommended_action"],
                        "final_status": m["final_status"], "similarity": round(s, 3)}
                       for m, s in hits],
    }


def investigate(break_id):
    """Builds the evidence bundle for one break."""
    breaks = _tables()["breaks"]
    if break_id not in breaks:
        raise KeyError(f"unknown break_id {break_id}")
    feed = break_feed(break_id)
    document = gather_document_evidence(feed)

    return {
        "break_id": break_id,
        "break_type": feed["break_type"],
        "severity": feed["severity"],
        "reported": {
            "field": feed["breaking_fields"],
            "expected": feed["source_value"],
            "observed": feed["target_value"],
            "source_system": feed["source_system"],
            "comparison_system": feed["comparison_system"],
        },
        "structured_evidence": gather_structured_evidence(feed["source_record_id"]),
        "document_evidence": document,
        "corporate_action_context": gather_ca_context(feed, document),
        # filled in by the RCA agent once there is a diagnosis
        "precedent_context": {"has_precedents": False, "precedents": []},
    }


if __name__ == "__main__":
    breaks = _tables()["breaks"]
    picks = []
    for fam in ["POSITION", "CASH", "SETTLEMENT", "TRADE"]:
        picks.append(next(bid for bid, b in breaks.items()
                          if b["break_type"] == fam and b["needs_evidence_bundle"] == "True"))
    picks.append(next(bid for bid, b in breaks.items() if b["corporate_action_type"]))

    for bid in picks:
        bundle = investigate(bid)
        doc = bundle["document_evidence"]
        ca = bundle["corporate_action_context"]
        print(f"\n{bid} ({bundle['break_type']}, field {bundle['reported']['field']})")
        print(f"  document: {doc.get('has_document')} via {doc.get('extraction_method')}, "
              f"{len(doc.get('related_documents', []))} related")
        if ca["is_corporate_action"] and ca["reference_entries"]:
            top = ca["reference_entries"][0]
            print(f"  CA reference: {top['action_type']} ({top['classification']})")
