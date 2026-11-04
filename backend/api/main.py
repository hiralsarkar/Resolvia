"""
REST API over the same pipeline the Streamlit app uses.

This is how another system (a ticketing tool, a reconciliation platform)
would drive Resolvia: open a case for a break, read the result, and record a
person's decision. Approval still only happens through record_decision().

Run from backend/:  uvicorn api.main:app --reload
"""

import os
import sys

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "agents"))

import control_gate  # noqa: E402
import auth  # noqa: E402
import orchestrator  # noqa: E402
from investigation import _tables, break_feed  # noqa: E402

app = FastAPI(title="Resolvia", description="Exception investigation and controlled resolution")


class Decision(BaseModel):
    decision: str  # APPROVE or REJECT
    approver: str
    notes: str | None = None


def _summary(case):
    rca = case.get("rca") or {}
    proposal = case.get("proposal") or {}
    return {
        "break_id": case["break_id"],
        "status": case["status"],
        "root_cause": rca.get("root_cause"),
        "confidence": rca.get("confidence"),
        "responsible_field": rca.get("field"),
        "expected_value": rca.get("expected"),
        "observed_value": rca.get("actual"),
        "explanation": rca.get("explanation"),
        "calculation": rca.get("entitlement_calculation"),
        "evidence_cited": rca.get("evidence_cited", []),
        "needs_person": rca.get("requires_human_decision"),
        "recommended_action": proposal.get("recommended_action"),
        "authority_tier": proposal.get("authority_tier"),
        "approval_required": proposal.get("approval_required"),
        "gate": (case.get("gate_result") or {}).get("reason"),
        "validation": case.get("validation"),
        "history": case["history"],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/breaks")
def list_breaks(family: str | None = None, severity: str | None = None, limit: int = 100):
    rows = []
    for bid in _tables()["breaks"]:
        feed = break_feed(bid)
        if family and feed["break_type"] != family.upper():
            continue
        if severity and feed["severity"] != severity.upper():
            continue
        case = orchestrator.get_case(bid)
        rows.append({"break_id": bid, "family": feed["break_type"], "severity": feed["severity"],
                     "field": feed["breaking_fields"], "expected": feed["source_value"],
                     "observed": feed["target_value"], "counterparty": feed["counterparty"],
                     "status": case["status"] if case else "NOT_STARTED"})
        if len(rows) >= limit:
            break
    return {"breaks": rows, "count": len(rows)}


@app.post("/cases/{break_id}")
def open_case(break_id: str):
    if break_id not in _tables()["breaks"]:
        raise HTTPException(404, f"no break {break_id}")
    case = orchestrator.get_case(break_id) or orchestrator.create_case(break_id)
    return _summary(case)


@app.get("/cases/{break_id}")
def get_case(break_id: str):
    case = orchestrator.get_case(break_id)
    if case is None:
        raise HTTPException(404, f"no case open for {break_id}")
    return _summary(case)


@app.post("/cases/{break_id}/decision")
def decide(break_id: str, body: Decision, x_operator_id: str | None = Header(default=None)):
    if orchestrator.get_case(break_id) is None:
        raise HTTPException(404, f"no case open for {break_id}")
    try:
        auth.require_actor(x_operator_id, ("analyst", "approver"))
        control_gate.record_decision(break_id, body.decision.upper(), body.approver, body.notes, actor_id=x_operator_id)
    except (ValueError, PermissionError) as e:
        raise HTTPException(400, str(e))
    return _summary(orchestrator.resume_case(break_id))
