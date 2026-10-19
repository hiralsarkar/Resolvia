import os
import sys
import pandas as pd
import streamlit as st

BACKEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend")
sys.path.insert(0, BACKEND_DIR)
sys.path.insert(0, os.path.join(BACKEND_DIR, "agents"))

import orchestrator  # noqa: E402
import control_gate  # noqa: E402
from investigation import _tables, break_feed  # noqa: E402
from theme import root_cause_label  # noqa: E402
from audit import record as _audit_record, list_events as _audit_events, summary as _audit_summary  # noqa: E402

# What the reconciliation engine says, in plain words, before any diagnosis.
REPORTED_ISSUE = {
    "actual_quantity": "Position quantity differs",
    "as_of_date": "Position date differs",
    "amount": "Cash amount differs",
    "amount,cash_id": "Cash postings don't match",
    "amount,currency": "Cash amount and currency differ",
    "ssi_code": "Settlement instruction differs",
    "settlement_date,settlement_status": "Settlement not completed on time",
    "instruction_status": "Settlement instruction status differs",
    "settlement_date": "Settlement date differs",
    "price": "Confirmed price differs",
    "quantity": "Confirmed quantity differs",
    "trade_date": "Confirmed trade date differs",
    "counterparty": "Confirmed counterparty differs",
    "confirmation": "Confirmation not received",
    "quantity,price": "Confirmed quantity and price differ",
}


@st.cache_data(show_spinner=False)
def load_breaks_df():
    """The break queue as the reconciliation engine hands it over.

    The generator's root-cause label is left out on purpose. The app only
    learns the cause from the RCA agent, the same as it would in production."""
    t = _tables()
    rows = []
    for bid in t["breaks"]:
        b = break_feed(bid)
        trade = t["trades"].get(b["source_record_id"], {})
        issue = REPORTED_ISSUE.get(b["breaking_fields"], b["breaking_fields"])
        if b["corporate_action_type"]:
            issue = f"Corporate action: {issue[0].lower()}{issue[1:]}"
        rows.append({
            "break_id": bid, "family": b["break_type"], "reported_issue": issue,
            "severity": b["severity"], "counterparty": b["counterparty"], "client": b["client"],
            "corporate_action": b["corporate_action_type"] or "",
            "needs_evidence": b["needs_evidence_bundle"] == "True",
            "exposure": float(trade.get("trade_value", 0) or 0),
            "security": trade.get("security", ""), "business_date": b["business_date"],
        })
    return pd.DataFrame(rows)


def diagnosed_cause(break_id):
    case = orchestrator.get_case(break_id)
    return ((case or {}).get("rca") or {}).get("root_cause")


def issue_label(row):
    """The diagnosis once RCA has run, otherwise what the break feed reported."""
    cause = diagnosed_cause(row.break_id)
    return root_cause_label(cause) if cause else row.reported_issue


def audit(action, break_id=None, detail="", actor_id=None, source="UI", metadata=None, dedupe_key=None):
    return _audit_record(actor_id or st.session_state.get("operator_id","OPS-1047"),action,break_id,detail,source,metadata,dedupe_key=dedupe_key)

def audit_events(**kwargs): return _audit_events(**kwargs)
def audit_summary(): return _audit_summary()

def _sync_case_audit(case):
    if not case: return
    bid=case.get("break_id")
    for i,e in enumerate(case.get("history",[])):
        audit(e.get("event","SYSTEM_EVENT"),bid,e.get("detail",""),actor_id="SYSTEM",source="CASE_PIPELINE",dedupe_key=f"case:{bid}:history:{i}:{e.get('event')}:{e.get('timestamp')}")

def get_case(break_id):
    case=orchestrator.get_case(break_id); _sync_case_audit(case); return case

def get_or_create_case(break_id,on_event=None):
    case=orchestrator.get_case(break_id)
    if case is None:
        audit("CASE_ANALYSIS_STARTED",break_id,"Analyst started the case pipeline")
        case=orchestrator.create_case(break_id,on_event=on_event)
    _sync_case_audit(case); return case

def resume_case(break_id,on_event=None):
    case=orchestrator.resume_case(break_id,on_event=on_event); _sync_case_audit(case); return case

def approve(break_id,approver,notes=None,on_event=None,mode="Controlled Action"):
    audit("APPROVAL_GRANTED",break_id,f"Approved by {approver}; execution mode: {mode}; notes: {notes or 'none'}")
    control_gate.record_decision(break_id,"APPROVE",approver,f"[{mode}] {notes or ''}".strip())
    case=orchestrator.get_case(break_id); case["execution_mode"]=mode; orchestrator._log(case,"EXECUTION_MODE",mode)
    audit("CONTROLLED_ACTION_SELECTED",break_id,f"Execution mode: {mode}")
    return resume_case(break_id,on_event=on_event)

def begin_manual(break_id,operator,notes=""):
    """Start a manual resolution without satisfying the execution gate.

    Selecting manual resolution is an execution choice, not an approval and
    never closes the case. The break remains open while the analyst performs
    the correction in the appropriate operational system.
    """
    case=orchestrator.get_case(break_id)
    if case is None: raise KeyError(f"no case exists for {break_id}")
    case["execution_mode"]="Manual"
    case["status"]="MANUAL_IN_PROGRESS"
    case["manual_resolution"]={"operator":operator,"started_at":pd.Timestamp.utcnow().isoformat(),"notes":notes,"actions":[],"evidence":[]}
    orchestrator._log(case,"MANUAL_RESOLUTION_STARTED",f"by {operator}: {notes or 'manual correction started'}")
    audit("MANUAL_RESOLUTION_STARTED",break_id,f"Manual resolution started by {operator}; {notes or 'no note'}",actor_id=operator)
    orchestrator.save(case)
    _sync_case_audit(case)
    return case

def submit_manual(break_id,operator,action_taken,evidence_reference,checklist):
    """Record the human-performed correction and move to verification.

    This does not call the execution simulator and
    does not close the case. Verification remains a separate control step.
    """
    case=orchestrator.get_case(break_id)
    if case is None: raise KeyError(f"no case exists for {break_id}")
    if case.get("status")!="MANUAL_IN_PROGRESS": raise ValueError("manual resolution has not been started")
    if not action_taken.strip(): raise ValueError("describe the action performed before submitting")
    if not evidence_reference.strip(): raise ValueError("provide a confirmation or evidence reference")
    if not all(checklist): raise ValueError("complete every required evidence check before submitting")
    case["manual_resolution"].update({"submitted_by":operator,"submitted_at":pd.Timestamp.utcnow().isoformat(),"action_taken":action_taken,"evidence_reference":evidence_reference,"checklist":checklist})
    case["status"]="AWAITING_VERIFICATION"
    orchestrator._log(case,"MANUAL_ACTION_SUBMITTED",f"by {operator}; evidence={evidence_reference}")
    audit("MANUAL_ACTION_SUBMITTED",break_id,f"Manual correction recorded by {operator}; evidence/reference: {evidence_reference}",actor_id=operator)
    orchestrator.save(case)
    _sync_case_audit(case)
    return case

def verify_manual(break_id,verifier,verification_notes):
    """Close a manually resolved case only after a separate verification step."""
    case=orchestrator.get_case(break_id)
    if case is None: raise KeyError(f"no case exists for {break_id}")
    if case.get("status")!="AWAITING_VERIFICATION": raise ValueError("case is not awaiting verification")
    if not verification_notes.strip(): raise ValueError("verification notes are required")
    case["manual_resolution"]["verified_by"]=verifier
    case["manual_resolution"]["verified_at"]=pd.Timestamp.utcnow().isoformat()
    case["manual_resolution"]["verification_notes"]=verification_notes
    case["status"]="CLOSED"
    orchestrator._log(case,"MANUAL_RESOLUTION_VERIFIED",f"verified by {verifier}: {verification_notes}")
    orchestrator._log(case,"CASE_CLOSED","manual resolution verified")
    audit("MANUAL_RESOLUTION_VERIFIED",break_id,f"Verified by {verifier}: {verification_notes}",actor_id=verifier)
    audit("CASE_CLOSED",break_id,"Case closed after independent manual-resolution verification",actor_id=verifier)
    orchestrator.save(case)
    _sync_case_audit(case)
    return case

def mark(break_id,status,approver,notes=None):
    audit("CASE_ESCALATED" if status=="ESCALATED" else "CASE_REVIEWED",break_id,f"{status} by {approver}; notes: {notes or 'none'}")
    case=orchestrator.get_case(break_id); case["status"]=status; orchestrator._log(case,"HUMAN_"+status,f"by {approver}: {notes or ''}".strip()); orchestrator.save(case); _sync_case_audit(case); return case

def reject(break_id,approver,notes=None):
    audit("APPROVAL_REJECTED",break_id,f"Rejected by {approver}; notes: {notes or 'none'}"); control_gate.record_decision(break_id,"REJECT",approver,notes); return resume_case(break_id)

def case_status(break_id):
    case=orchestrator.get_case(break_id); return case["status"] if case else "NOT_STARTED"

def all_case_statuses(): return orchestrator.case_statuses()

@st.cache_data(show_spinner=False)
def resolved_cases_summary():
    path=os.path.join(BACKEND_DIR,"knowledge","resolved_cases.json")
    if not os.path.exists(path): return {"n":0,"n_closed":0,"n_reopened":0}
    import json
    with open(path,encoding="utf-8") as f: cases=json.load(f)
    return {"n":len(cases),"n_closed":sum(1 for c in cases if c["final_status"]=="CLOSED"),"n_reopened":sum(1 for c in cases if c["final_status"]=="REOPENED"),"n_on_hold":sum(1 for c in cases if c["final_status"]=="ON_HOLD")}

def summary_kpis():
    df=load_breaks_df(); statuses=all_case_statuses(); n_total=len(df); n_cased=len(statuses); n_closed=sum(s=="CLOSED" for s in statuses.values()); n_awaiting=sum(s=="AWAITING_APPROVAL" for s in statuses.values()); n_reopened=sum(s=="REOPENED" for s in statuses.values())
    return {"n_total":n_total,"n_cased":n_cased,"n_closed":n_closed,"n_awaiting":n_awaiting,"n_reopened":n_reopened,"total_exposure":df["exposure"].sum(),"ca_count":(df["corporate_action"]!="").sum()}
