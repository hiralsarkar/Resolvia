"""Shared test setup: an in-memory database, import paths, and a stand-in for
the sentence-transformers model so tests run offline and fast."""
import hashlib
import os
import sys

import numpy as np

os.environ["RESOLVIA_DB"] = ":memory:"
os.environ["RESOLVIA_INVESTIGATOR"] = "off"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in ("data", "backend", "backend/agents", "backend/embeddings", "backend/eval"):
    sys.path.insert(0, os.path.join(ROOT, p))

import embed_store  # noqa: E402


class _StandInEncoder:
    """Deterministic vectors with no meaning. Retrieval still runs end to end."""
    def encode(self, texts, show_progress_bar=False, normalize_embeddings=True):
        out = []
        for t in texts:
            v = np.random.default_rng(int(hashlib.md5(t.encode()).hexdigest()[:8], 16)).normal(size=384)
            out.append(v / np.linalg.norm(v))
        return np.array(out, dtype=np.float32)


embed_store._MODEL = _StandInEncoder()

import warnings  # noqa: E402
warnings.filterwarnings("ignore")


def document(doc_id):
    with open(os.path.join(ROOT, "data", "broker_confirms", f"{doc_id}.txt"), encoding="utf-8") as f:
        return f.read()


def first_break(root_cause):
    import investigation
    return next(b for b, r in investigation._tables()["breaks"].items() if r["mismatch_type"] == root_cause)
