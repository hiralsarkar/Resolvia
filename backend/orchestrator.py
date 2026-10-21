"""
Orchestrator.

The workflow is a LangGraph state graph. The case is the graph's state, each
agent is a node, and conditional edges decide where a case goes next based on
what the agents found.

    START -> triage -> investigate -> rca -> propose -> gate -> execute -> validate -> END

  - Bad data at Triage ends the case as HALTED_DATA_QUALITY.
  - After RCA, a case with unusual signals goes to the Investigator Agent
    first: an LLM with read-only tools that decides for itself what else to
    look at, loops until it has a finding, and hands the case on to propose.
  - At the gate, an action that needs a person pauses the graph with a
    LangGraph interrupt. The case waits as AWAITING_APPROVAL; once someone
    records a decision with control_gate.record_decision(), resume_case()
    resumes the graph from that exact point. A rejection ends it as REJECTED.
  - Validation ends the case as CLOSED, REOPENED or ON_HOLD.

A checkpointer keeps every paused run, and each finished run is also saved
to SQLite (store.py), so cases and their history survive a restart. If the
process restarts while a case is paused, resume_case() starts a fresh run
from the saved case and the entry router sends it straight to the stage it
had reached.

The one decision the Orchestrator owns is routing. Whether an action needs
approval is the Control Gate's call, and the graph has no path to execution
that doesn't go through the gate.
"""

import copy
import os
import sys
import threading
from datetime import datetime, timezone
from typing import TypedDict
from uuid import uuid4

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "agents"))
sys.path.insert(0, HERE)

import triage  # noqa: E402
import investigation  # noqa: E402
import investigator  # noqa: E402
import rca  # noqa: E402
import resolution  # noqa: E402
import control_gate  # noqa: E402
import execution_simulator  # noqa: E402
import store  # noqa: E402
from validation import validate  # noqa: E402


class CaseState(TypedDict, total=False):
    break_id: str
    status: str
    history: list
    triage: dict
    investigation: dict
    rca: dict
    further_investigation: dict
    proposal: dict
    gate_result: dict
    post_execution: dict
    validation: dict


FIELDS = tuple(CaseState.__annotations__)
_CASES = {}  # in-memory cache; store.py is the record
_HOOK = threading.local()


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _log(case, event, detail=""):
    """Appends to a case's history. Used by the app for actions outside the graph."""
    case["history"].append({"event": event, "detail": detail, "timestamp": _now()})


def _add(history, event, detail=""):
    return history + [{"event": event, "detail": detail, "timestamp": _now()}]


def _fire(stage, label, detail):
    """Progress hook for the UI. It never changes the flow."""
    hook = getattr(_HOOK, "fn", None)
    if hook:
        hook(stage, label, detail)


def _plain(x):
    """numpy scalars to plain Python, so a state can be checkpointed."""
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if hasattr(x, "item") and type(x).__module__ == "numpy":
        return x.item()
    if isinstance(x, str) and type(x) is not str:
        return str(x)
    return x


def _new_case(break_id):
    return {"break_id": break_id, "status": "CASE_CREATED", "history": [],
            **{f: None for f in FIELDS if f not in ("break_id", "status", "history")}}


# nodes

def n_triage(s):
    t = _plain(triage.triage(s["break_id"]))
    h = _add(s["history"], "TRIAGE_COMPLETE",
             f"family={t['predicted_family']} priority={t['priority']} route={t['route']}")
    _fire("triage", "Triage Agent", f"routed to {t['route']}, priority {t['priority']}")
    if not t["valid"]:
        return {"triage": t, "status": "HALTED_DATA_QUALITY",
                "history": _add(h, "CASE_HALTED", "; ".join(t["validation_issues"]))}
    return {"triage": t, "history": h}


def n_investigate(s):
    ev = _plain(investigation.investigate(s["break_id"]))
    has_doc = ev["document_evidence"].get("has_document", False)
    _fire("investigation", "Investigation Agent", "evidence gathered" + (", document read" if has_doc else ""))
    return {"investigation": ev, "history": _add(s["history"], "INVESTIGATION_COMPLETE", f"has_document={has_doc}")}


def n_rca(s):
    r = _plain(rca.analyze(s["break_id"], evidence=copy.deepcopy(s["investigation"])))
    h = _add(s["history"], "RCA_COMPLETE", f"root_cause={r['root_cause']} confidence={r['confidence']:.2f} "
                                           f"requires_human_decision={r['requires_human_decision']}")
    if (r.get("document_finding") or {}).get("changed"):
        h = _add(h, "RCA_DOCUMENT_OVERRIDE", f"model said {r['document_finding']['model_said']}, notice says "
                                             f"{r['document_finding']['mandatory_flag']}")
    _fire("rca", "RCA Agent", f"{r['root_cause']} at {r['confidence'] * 100:.1f}% confidence")
    return {"rca": r, "history": h}


def n_investigator(s):
    f = _plain(investigator.investigate_further(s))
    tools = ", ".join(step["tool"] for step in f["steps"]) or "none"
    h = _add(s["history"], "FURTHER_INVESTIGATION",
             f"signals: {'; '.join(f['signals'])}. status={f['status']}, tools used: {tools}")
    if f["finding"] and f["status"] == "COMPLETE":
        h = _add(h, "INVESTIGATOR_FINDING", f["finding"])
    _fire("investigator", "Investigator Agent", f"looked further: {len(f['steps'])} checks")
    return {"further_investigation": f, "history": h}


def n_propose(s):
    p = _plain(resolution.propose(s["break_id"], rca_result=copy.deepcopy(s["rca"]),
                                  evidence=copy.deepcopy(s["investigation"])))
    f = s.get("further_investigation") or {}
    if f.get("status") == "COMPLETE":
        p["approval_required"] = True
        p["investigator_finding"] = f["finding"]
    _fire("proposal", "Resolution Proposal Agent", p["authority_tier"].replace("_", " "))
    return {"proposal": p, "history": _add(
        s["history"], "RESOLUTION_PROPOSAL_COMPLETE",
        f"action={p['recommended_action'][:70]!r} authority_tier={p['authority_tier']} "
        f"approval_required={p['approval_required']}")}


def n_gate(s):
    g = _plain(control_gate.check_gate(s["proposal"]))
    h = _add(s["history"], "GATE_CHECK:" + ("AUTHORIZED" if g["authorized"] else "BLOCKED"), g["reason"])
    _fire("gate", "Orchestrator", "gate authorised, continuing" if g["authorized"]
          else "gate blocked, waiting for a person")
    out = {"gate_result": g, "history": h}
    if not g["authorized"]:
        decision = control_gate.get_decision(s["break_id"])
        if decision and decision["decision"] == "REJECT":
            out.update(status="REJECTED", history=_add(h, "CASE_REJECTED", f"by {decision['approver']}"))
        else:
            out["status"] = "AWAITING_APPROVAL"
    return out


def n_await_approval(s):
    """Pauses the graph until a person has decided. Resumed by resume_case()."""
    interrupt({"break_id": s["break_id"], "reason": s["gate_result"]["reason"]})
    return {}


def n_execute(s):
    feed = investigation.break_feed(s["break_id"])
    post = _plain(execution_simulator.execute(copy.deepcopy(s["proposal"]), copy.deepcopy(s["investigation"]), feed))
    _fire("post_execution", "Execution", "fix applied")
    return {"post_execution": post, "history": _add(
        s["history"], "EXECUTION_COMPLETE", f"applied fix for {s['proposal']['root_cause']}")}


def n_validate(s):
    feed = investigation.break_feed(s["break_id"])
    v = _plain(validate(s["break_id"], feed, copy.deepcopy(s["post_execution"]), copy.deepcopy(s["proposal"])))
    _fire("validation", "Validation Agent", v["status"])
    h = _add(_add(s["history"], "VALIDATION_COMPLETE", v["reason"]), f"CASE_{v['status']}")
    _fire("done", "Orchestrator", f"case {v['status'].lower().replace('_', ' ')}")
    return {"validation": v, "status": v["status"], "history": h}


# routing

def after_rca(s):
    if s.get("further_investigation") is None and investigator.unusual_signals(s):
        return "investigator"
    return "propose"


def entry(s):
    """Sends a case to the first stage it hasn't completed."""
    if s.get("triage") is None:
        return "triage"
    if not s["triage"]["valid"]:
        return END
    if s.get("investigation") is None:
        return "investigate"
    if s.get("rca") is None:
        return "rca"
    if s.get("proposal") is None:
        return after_rca(s)
    return "gate"


def after_triage(s):
    return "investigate" if s["triage"]["valid"] else END


def after_gate(s):
    if s["gate_result"]["authorized"]:
        return "validate" if s.get("post_execution") else "execute"
    return END if s.get("status") == "REJECTED" else "await_approval"


def build_graph(checkpointer=None):
    g = StateGraph(CaseState)
    for name, fn in [("triage", n_triage), ("investigate", n_investigate), ("rca", n_rca),
                     ("investigator", n_investigator), ("propose", n_propose), ("gate", n_gate),
                     ("await_approval", n_await_approval), ("execute", n_execute), ("validate", n_validate)]:
        g.add_node(name, fn)
    g.add_conditional_edges(START, entry, ["triage", "investigate", "rca", "investigator", "propose", "gate", END])
    g.add_conditional_edges("triage", after_triage, ["investigate", END])
    g.add_edge("investigate", "rca")
    g.add_conditional_edges("rca", after_rca, ["investigator", "propose"])
    g.add_edge("investigator", "propose")
    g.add_edge("propose", "gate")
    g.add_conditional_edges("gate", after_gate, ["execute", "validate", "await_approval", END])
    g.add_edge("await_approval", "gate")
    g.add_edge("execute", "validate")
    g.add_edge("validate", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())


GRAPH = build_graph()


def mermaid():
    """The graph as a Mermaid diagram."""
    return GRAPH.get_graph().draw_mermaid()


# running a case

def _run(case, on_event=None):
    """Runs or resumes the graph for one case and merges the result back in.

    The app can add to a case between runs (an execution mode, a note), so the
    saved case stays the record: the graph's new history entries are appended
    to it and its stage results are written over it."""
    case.setdefault("thread_id", f"{case['break_id']}:{uuid4().hex[:8]}")
    config = {"configurable": {"thread_id": case["thread_id"]}}
    _HOOK.fn = on_event
    try:
        paused = GRAPH.get_state(config)
        if paused.next:
            before = paused.values
            decision = control_gate.get_decision(case["break_id"]) or {"decision": None}
            GRAPH.invoke(Command(resume=decision), config)
        else:
            before = copy.deepcopy({f: case.get(f) for f in FIELDS})
            GRAPH.invoke(before, config)
        after = GRAPH.get_state(config).values
    finally:
        _HOOK.fn = None
    new_history = after["history"][len(before["history"]):]
    case.update({k: v for k, v in after.items() if k != "history"})
    case["history"].extend(new_history)
    return case


def save(case):
    """Writes the case to the database. The pipeline saves after every run;
    anything else that changes a case (the app's manual workflow) calls this."""
    store.save_case(case)
    return case


def create_case(break_id, on_event=None):
    if get_case(break_id) is not None:
        raise ValueError(f"a case for {break_id} already exists, use resume_case() or get_case()")
    case = _CASES[break_id] = _new_case(break_id)
    _log(case, "CASE_CREATED")
    return save(_run(case, on_event=on_event))


def resume_case(break_id, on_event=None):
    """Call after control_gate.record_decision(). Resumes the graph at the gate."""
    case = get_case(break_id)
    if case is None:
        raise KeyError(f"no case for {break_id}, call create_case() first")
    return save(_run(case, on_event=on_event))


def get_case(break_id):
    if break_id not in _CASES:
        stored = store.load_case(break_id)
        if stored is None:
            return None
        _CASES[break_id] = stored
    return _CASES[break_id]


def case_statuses():
    return store.case_statuses()


def reset():
    global GRAPH
    _CASES.clear()
    store.reset("cases")
    GRAPH = build_graph()


if __name__ == "__main__":
    os.environ.setdefault("RESOLVIA_DB", ":memory:")
    control_gate.reset()
    reset()
    print(mermaid())
    breaks = investigation._tables()["breaks"]

    ssi = next(b for b, r in breaks.items() if r["mismatch_type"] == "SETL_WRONG_SSI")
    case = create_case(ssi)
    print(f"{ssi} after create_case: {case['status']}")
    control_gate.record_decision(ssi, "APPROVE", "ops.head@resolvia.local", notes="SSI checked with custodian")
    case = resume_case(ssi)
    print(f"{ssi} after approval: {case['status']}\n")
    for e in case["history"]:
        print(f"  {e['timestamp']}  {e['event']:30s} {e['detail']}")
