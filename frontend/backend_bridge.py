"""Thin Streamlit-side wrapper around the backend.

All case state, approvals and the audit trail are persisted by the backend
(backend/case_store.py, SQLite), so nothing here lives only in the browser
session: a page reload or a server restart picks up exactly where the team
left off. The workflow logic itself is in backend/workflow.py; this module only
adds the signed-in Operations ID and Streamlit caching.
"""
import os
import sys

import pandas as pd
import streamlit as st

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "agents"))

import orchestrator  # noqa: E402
import control_gate  # noqa: E402
import case_store  # noqa: E402
import clock  # noqa: E402
import workflow  # noqa: E402
from investigation import _tables  # noqa: E402
import audit as _audit  # noqa: E402

DECISION_STATUSES = workflow.DECISION_STATUSES
MANUAL_START_STATUSES = workflow.MANUAL_START_STATUSES
OPEN_EXCLUDED = {"CLOSED", "REJECTED"}


def operator():
    return st.session_state.get("operator_id", "OPS-1047")


@st.cache_data(show_spinner=False)
def load_breaks_df():
    t = _tables()
    rows = []
    for bid, b in t["breaks"].items():
        trade = t["trades"].get(b["source_record_id"], {})
        rows.append({"break_id": bid, "family": b["break_type"], "root_cause_key": b["mismatch_type"],
                     "root_cause": b["root_cause"], "severity": b["severity"], "counterparty": b["counterparty"],
                     "client": b["client"], "corporate_action": b["corporate_action_type"] or "",
                     "needs_evidence": b["needs_evidence_bundle"] == "True",
                     "exposure": float(trade.get("trade_value", 0) or 0), "security": trade.get("security", ""),
                     "business_date": b["business_date"]})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------- audit

def audit(action, break_id=None, detail="", actor_id=None, source="UI", metadata=None, dedupe_key=None):
    return _audit.record(actor_id or operator(), action, break_id, detail, source, metadata, dedupe_key=dedupe_key)


def audit_events(**kwargs):
    return _audit.list_events(**kwargs)


def audit_count(**kwargs):
    return _audit.count(**kwargs)


def audit_distinct(column):
    return _audit.distinct(column)


def audit_summary(**kwargs):
    return _audit.summary(**kwargs)


# ---------------------------------------------------------------- cases

def get_case(break_id):
    return workflow.get_case(break_id)


def get_or_create_case(break_id, on_event=None):
    return workflow.start_case(break_id, operator(), on_event=on_event)


def resume_case(break_id, on_event=None):
    return workflow.resume_case(break_id, on_event=on_event)


def approve(break_id, approver, notes=None, on_event=None, mode="Assisted"):
    return workflow.approve(break_id, approver or operator(), notes, mode=mode, on_event=on_event)


def begin_manual(break_id, operator_id, notes=""):
    return workflow.begin_manual(break_id, operator_id or operator(), notes)


def submit_manual(break_id, operator_id, action_taken, evidence_reference, checklist):
    return workflow.submit_manual(break_id, operator_id or operator(), action_taken, evidence_reference, checklist)


def verify_manual(break_id, verifier, verification_notes):
    return workflow.verify_manual(break_id, verifier, verification_notes)


def mark(break_id, status, approver, notes=None):
    return workflow.mark(break_id, status, approver or operator(), notes)


def reject(break_id, approver, notes=None):
    return workflow.reject(break_id, approver or operator(), notes)


def resolution_record(case):
    return workflow.resolution_record(case)


def case_status(break_id):
    case = orchestrator.get_case(break_id)
    return case["status"] if case else "NOT_STARTED"


def all_case_statuses():
    return {bid: c["status"] for bid, c in orchestrator._CASES.items()}


def last_updates():
    """break_id -> timestamp of the last recorded step, for the queue."""
    return {bid: (c["history"][-1]["timestamp"] if c.get("history") else "") for bid, c in orchestrator._CASES.items()}


# ---------------------------------------------------------------- supplemental evidence (persisted)

def supplemental_documents(break_id):
    return case_store.list_supplemental(break_id, "document")


def add_supplemental_document(break_id, record):
    case_store.add_supplemental(break_id, "document", record, created_at=record.get("uploaded_at"))


def supplemental_reviews(break_id):
    return case_store.list_supplemental(break_id, "review")


def add_supplemental_review(break_id, review):
    case_store.add_supplemental(break_id, "review", review, created_at=review.get("created_at"))


def now_iso():
    return clock.now_iso()


# ---------------------------------------------------------------- portfolio views

@st.cache_data(show_spinner=False)
def resolved_cases_summary():
    path = os.path.join(BACKEND_DIR, "knowledge", "resolved_cases.json")
    if not os.path.exists(path):
        return {"n": 0, "n_closed": 0, "n_reopened": 0}
    import json
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    return {"n": len(cases), "n_closed": sum(1 for c in cases if c["final_status"] == "CLOSED"),
            "n_reopened": sum(1 for c in cases if c["final_status"] == "REOPENED")}


def summary_kpis():
    df = load_breaks_df()
    statuses = all_case_statuses()
    n_total = len(df)
    n_closed = sum(s == "CLOSED" for s in statuses.values())
    return {"n_total": n_total, "n_cased": len(statuses), "n_closed": n_closed,
            "pct_closed": n_closed / n_total if n_total else 0.0,
            "n_open": n_total - sum(s in OPEN_EXCLUDED for s in statuses.values()),
            "n_awaiting": sum(s == "AWAITING_APPROVAL" for s in statuses.values()),
            "n_reopened": sum(s == "REOPENED" for s in statuses.values()),
            "total_exposure": df["exposure"].sum(), "ca_count": (df["corporate_action"] != "").sum()}


def storage_info():
    return {"path": case_store.path(), "persistent": case_store.is_persistent(),
            "seed": case_store.get_meta("seed")}


def reset_demo():
    workflow.reset_demo()
