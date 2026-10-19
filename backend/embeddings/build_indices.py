"""
Builds the three embedding indexes and saves them to embeddings/saved/.

Rerun it whenever the documents, ca_reference.json or resolved_cases.json
change. Run knowledge/build_resolved_cases.py first if the precedent corpus
needs refreshing.
"""

import csv
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from embed_store import EmbeddingStore

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
KNOWLEDGE_DIR = os.path.join(HERE, "..", "knowledge")
SAVED_DIR = os.path.join(HERE, "saved")


def build_evidence_index():
    with open(os.path.join(DATA_DIR, "broker_confirms_mapping.csv"), newline="") as f:
        mapping = list(csv.DictReader(f))

    texts, metadata = [], []
    for row in mapping:
        doc_path = os.path.join(DATA_DIR, "broker_confirms", f"{row['doc_id']}.txt")
        with open(doc_path, encoding="utf-8") as f:
            texts.append(f.read())
        metadata.append(row)

    store = EmbeddingStore().build(texts, metadata)
    store.save(os.path.join(SAVED_DIR, "evidence_index"))
    print(f"Evidence index: {len(texts)} documents")
    return store


def build_ca_reference_index():
    with open(os.path.join(KNOWLEDGE_DIR, "ca_reference.json"), encoding="utf-8") as f:
        entries = json.load(f)

    texts = [e["text"] for e in entries]
    store = EmbeddingStore().build(texts, entries)
    store.save(os.path.join(SAVED_DIR, "ca_reference_index"))
    print(f"CA reference index: {len(texts)} entries")
    return store


def build_resolved_cases_index():
    """The precedent cases. Run knowledge/build_resolved_cases.py first if
    resolved_cases.json is missing or the data has been regenerated."""
    path = os.path.join(KNOWLEDGE_DIR, "resolved_cases.json")
    if not os.path.exists(path):
        print("resolved_cases.json not found - run build_resolved_cases.py first, skipping")
        return None
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)

    texts = [
        f"{c['root_cause_desc']} | {c['family']} | action: {c['recommended_action']} | "
        f"outcome: {c['final_status']} | " + "; ".join(c["evidence_cited"])
        for c in cases
    ]
    store = EmbeddingStore().build(texts, cases)
    store.save(os.path.join(SAVED_DIR, "resolved_cases_index"))
    print(f"Resolved-cases (precedent) index: {len(texts)} cases")
    return store


if __name__ == "__main__":
    os.makedirs(SAVED_DIR, exist_ok=True)
    build_evidence_index()
    build_ca_reference_index()
    build_resolved_cases_index()
