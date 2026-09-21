"""
backend_bridge.py

Wires the frontend to the REAL backend (orchestrator.py + the 5 agents +
control_gate) - nothing in this app is mocked or hand-written sample
data. `backend/` modules already do their own module-level caching
(the _TABLES / _MODEL_BUNDLE / _CASES singletons), and Python module
state persists across Streamlit reruns within the same server process,
so most of that caching is free here. st.cache_data is used only for
the one genuinely expensive per-rerun cost: rebuilding the breaks
DataFrame from CSV on every script rerun (Streamlit reruns the whole
script on every interaction).

Cases are created lazily (get_or_create_case) - opening all 3000 cases
eagerly would mean running the embedding/OCR-capable pipeline on all
of them before the app even renders. Only breaks the user actually
opens in Case Investigation get a real Triage->...->Gate run.
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
from investigation import _tables  # noqa: E402


@st.cache_data(show_spinner=False)
def load_breaks_df():
    t = _tables()
    rows = []
    for bid, b in t["breaks"].items():
        trade = t["trades"].get(b["source_record_id"], {})
        rows.append({
            "break_id": bid, "family": b["break_type"], "root_cause_key": b["mismatch_type"],
            "root_cause": b["root_cause"], "severity": b["severity"],
            "counterparty": b["counterparty"], "client": b["client"],
            "corporate_action": b["corporate_action_type"] or "",
            "needs_evidence": b["needs_evidence_bundle"] == "True",
            "exposure": float(trade.get("trade_value", 0) or 0),
            "security": trade.get("security", ""), "business_date": b["business_date"],
        })
    return pd.DataFrame(rows)


def get_case(break_id):
    return orchestrator.get_case(break_id)


def get_or_create_case(break_id, on_event=None):
    case = orchestrator.get_case(break_id)
    if case is None:
        case = orchestrator.create_case(break_id, on_event=on_event)
    return case


def resume_case(break_id, on_event=None):
    return orchestrator.resume_case(break_id, on_event=on_event)


def approve(break_id, approver, notes=None, on_event=None, mode="Controlled Action"):
    """mode: how the approved fix is carried out - 'Controlled Action' (the
    system executes it) or 'Manually by Analyst'. Recorded on the case and in
    the gate audit note; the simulated repair + validation still run either
    way (a manual fix is re-verified exactly like a system one)."""
    control_gate.record_decision(break_id, "APPROVE", approver, f"[{mode}] {notes or ''}".strip())
    case = orchestrator.get_case(break_id)
    case["execution_mode"] = mode
    orchestrator._log(case, "EXECUTION_MODE", mode)
    return orchestrator.resume_case(break_id, on_event=on_event)


def mark(break_id, status, approver, notes=None):
    """Non-final human choices: IN_REVIEW or ESCALATED. The gate stays closed."""
    case = orchestrator.get_case(break_id)
    case["status"] = status
    orchestrator._log(case, "HUMAN_" + status, f"by {approver}: {notes or ''}".strip())
    return case


def reject(break_id, approver, notes=None):
    control_gate.record_decision(break_id, "REJECT", approver, notes)
    return orchestrator.resume_case(break_id)


def case_status(break_id):
    """Status for display even if the case hasn't been opened yet."""
    case = orchestrator.get_case(break_id)
    return case["status"] if case else "NOT_STARTED"


def all_case_statuses():
    """break_id -> status for every break that HAS a case, for the
    Operations Desk / Analytics views. Breaks never opened are simply
    absent (caller treats missing as NOT_STARTED)."""
    return {bid: c["status"] for bid, c in orchestrator._CASES.items()}


@st.cache_data(show_spinner=False)
def resolved_cases_summary():
    """The system's actual production track record - 400 cases run
    through this same Orchestrator in a seeding pass (see
    backend/knowledge/build_resolved_cases.py), distinct from whatever
    this particular browser session has processed live. Session state
    is in-memory and starts empty on every server restart, so without
    this the Analytics page reads as if the system has barely done
    anything - it hasn't; it just hasn't been asked to re-run 3000
    cases live in this tab."""
    path = os.path.join(BACKEND_DIR, "knowledge", "resolved_cases.json")
    if not os.path.exists(path):
        return {"n": 0, "n_closed": 0, "n_reopened": 0}
    import json
    with open(path, encoding="utf-8") as f:
        cases = json.load(f)
    return {
        "n": len(cases),
        "n_closed": sum(1 for c in cases if c["final_status"] == "CLOSED"),
        "n_reopened": sum(1 for c in cases if c["final_status"] == "REOPENED"),
    }


def summary_kpis():
    df = load_breaks_df()
    statuses = all_case_statuses()
    n_total = len(df)
    n_cased = len(statuses)
    n_closed = sum(1 for s in statuses.values() if s == "CLOSED")
    n_awaiting = sum(1 for s in statuses.values() if s == "AWAITING_APPROVAL")
    n_reopened = sum(1 for s in statuses.values() if s == "REOPENED")
    total_exposure = df["exposure"].sum()
    return {
        "n_total": n_total, "n_cased": n_cased, "n_closed": n_closed,
        "n_awaiting": n_awaiting, "n_reopened": n_reopened,
        "total_exposure": total_exposure,
        "ca_count": (df["corporate_action"] != "").sum(),
    }
