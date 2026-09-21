"""
embed_store.py

Minimal local embedding index - sentence-transformers (all-MiniLM-L6-v2,
frozen, pretrained) for vectors, plain numpy
cosine similarity for retrieval. No pgvector/Supabase - a local index is
sufficient at this corpus size (a few thousand documents).

Two indices are built by build_indices.py:
  - evidence documents (backend/embeddings/saved/evidence_index.*)
  - corporate-action reference KB (backend/embeddings/saved/ca_reference_index.*)

RAG has two uses here: (1) evidence retrieval - given a
break, find semantically related documents even without an explicit
break_id->doc_id join; (2) knowledge grounding - given a CA-flagged
break, retrieve the relevant action-type definition before an agent
judges mandatory vs voluntary. Precedent retrieval over resolved_cases
is built separately (see build_resolved_cases.py).
"""

import json
import os
import numpy as np

_MODEL = None


def get_model():
    global _MODEL
    if _MODEL is None:
        from sentence_transformers import SentenceTransformer
        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    return _MODEL


class EmbeddingStore:
    def __init__(self):
        self.vectors = None  # (n, d) float32, L2-normalized
        self.metadata = []   # list of dicts, one per row

    def build(self, texts, metadata):
        assert len(texts) == len(metadata)
        model = get_model()
        vecs = model.encode(texts, show_progress_bar=False, normalize_embeddings=True)
        self.vectors = np.asarray(vecs, dtype=np.float32)
        self.metadata = metadata
        return self

    def query(self, text, top_k=3):
        model = get_model()
        q = model.encode([text], show_progress_bar=False, normalize_embeddings=True)[0]
        sims = self.vectors @ q  # cosine similarity, both sides L2-normalized
        top_idx = np.argsort(-sims)[:top_k]
        return [(self.metadata[i], float(sims[i])) for i in top_idx]

    def save(self, path_prefix):
        np.save(f"{path_prefix}.npy", self.vectors)
        with open(f"{path_prefix}.meta.json", "w", encoding="utf-8") as f:
            json.dump(self.metadata, f)

    @classmethod
    def load(cls, path_prefix):
        store = cls()
        store.vectors = np.load(f"{path_prefix}.npy")
        with open(f"{path_prefix}.meta.json", encoding="utf-8") as f:
            store.metadata = json.load(f)
        return store

    def exists(self, path_prefix):
        return os.path.exists(f"{path_prefix}.npy")
