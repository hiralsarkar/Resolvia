"""
Resolvia backend - FastAPI skeleton.

Week 1: just a health check and a placeholder route per pipeline stage,
so the app boots and the folder structure has something real behind it.
Each route gets filled in as its agent/model is built (see /backend/agents,
/backend/models).
"""

from fastapi import FastAPI

app = FastAPI(title="Resolvia - AI-Native Trade Reconciliation")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/breaks")
def list_breaks():
    """Week 2+: return classified breaks from the Matching/Classification
    pipeline. Placeholder until the Ingestion + Matching agents exist."""
    return {"breaks": [], "note": "pipeline not wired up yet"}
