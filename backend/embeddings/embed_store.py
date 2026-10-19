"""
A small local vector index.

Vectors come from sentence-transformers (all-MiniLM-L6-v2, used as-is) and
search is a dot product in NumPy. At a few thousand documents that's all you
need; there's no vector database.

build_indices.py builds three of these: the evidence documents, the
corporate-action reference entries and the resolved precedent cases.
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
