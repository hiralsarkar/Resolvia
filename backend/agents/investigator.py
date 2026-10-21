"""
Investigator Agent: the one that decides for itself what to look at next.

Most breaks are explained by the records the Investigation Agent already
gathered, and the case goes straight on to a proposal. When something about a
case is unusual, the Orchestrator sends it here first. The signals:

  - the root-cause model's confidence is below the review threshold
  - the corporate action notice contradicted the model
  - Triage's family disagrees with the family the reconciliation engine tagged

The Investigator is a small LangGraph loop. An LLM reads the case, picks a
read-only tool (search trades by other keys, pull cash entries, read a
settlement record, search documents, the corporate action reference or past
cases), reads the result and decides what to check next. When it has enough,
it writes a short finding. Everything it looked at is recorded step by step.

        think --(tool calls)--> act --> think --> ... --> finding

It has read-only authority. Its finding goes into the case for the reviewer,
and a case it has worked on always goes to a person before any action.
"""

import json
import operator
import os
import sys
import threading
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))

import investigation  # noqa: E402
import llm  # noqa: E402
import rca  # noqa: E402

MAX_ROUNDS = 3        # rounds of tool calls before it has to conclude
MAX_RESULT_CHARS = 3000
QUIET = threading.local()  # set QUIET.on = True in a thread that runs cases in bulk

SYSTEM = """You are the investigator in a post-trade break resolution system at an \
investment bank. A break has unusual signals. Use the tools to check the evidence: \
look for the trade under other keys, related cash or settlement entries, documents, \
corporate action definitions and similar past cases. Call only the tools you need. \
Then finish with a short finding (at most 120 words): what you checked, what you \
found, and which root cause the evidence supports. You recommend; you never change \
records."""


# tools, all read-only

def _rows(table):
    return investigation._tables()[table]


def _clean(row):
    return {k: v for k, v in row.items() if k != "split"}


def find_trades(ticker=None, counterparty=None, trade_date=None, quantity=None, limit=5):
    """Trades matching any combination of keys. Useful when references don't line up."""
    hits = []
    for t in _rows("trades").values():
        if ticker and t["ticker"] != ticker.upper():
            continue
        if counterparty and t["counterparty"] != counterparty:
            continue
        if trade_date and t["trade_date"] != trade_date:
            continue
        if quantity and str(t["quantity"]) != str(quantity):
            continue
        hits.append(_clean(t))
        if len(hits) >= limit:
            break
    return hits


def cash_entries(trade_id=None, account=None, value_date=None, limit=10):
    """Cash ledger entries for a trade, or for an account on a value date."""
    if trade_id:
        return [_clean(r) for r in _rows("cash").get(trade_id, [])][:limit]
    hits = []
    for rows in _rows("cash").values():
        for r in rows:
            if account and r["account"] != account:
                continue
            if value_date and r["value_date"] != value_date:
                continue
            hits.append(_clean(r))
            if len(hits) >= limit:
                return hits
    return hits


def settlement_record(trade_id):
    """The settlement instruction and status for a trade."""
    row = _rows("settlements").get(trade_id)
    return _clean(row) if row else None


def _search(index_name, query, top_k, fields):
    index = investigation._index(index_name)
    if index is None:
        return []
    return [dict({f: m.get(f) for f in fields}, similarity=round(s, 3)) for m, s in index.query(query, top_k=top_k)]


def search_documents(query, top_k=3):
    """Broker confirmations, emails and notices most similar to the query."""
    return _search("evidence_index", query, top_k, ("doc_id", "break_id", "text"))


def corporate_action_reference(query, top_k=2):
    """Corporate action definitions most similar to the query."""
    return _search("ca_reference_index", query, top_k, ("action_type", "classification", "text"))


def similar_cases(query, top_k=3):
    """Past resolved cases most similar to the query."""
    return _search("resolved_cases_index", query, top_k,
                   ("break_id", "root_cause", "recommended_action", "final_status"))


TOOLS = {
    "find_trades": (find_trades, {
        "ticker": {"type": "string"}, "counterparty": {"type": "string"},
        "trade_date": {"type": "string", "description": "YYYY-MM-DD"}, "quantity": {"type": "integer"}}),
    "cash_entries": (cash_entries, {
        "trade_id": {"type": "string"}, "account": {"type": "string"},
        "value_date": {"type": "string", "description": "YYYY-MM-DD"}}),
    "settlement_record": (settlement_record, {"trade_id": {"type": "string"}}),
    "search_documents": (search_documents, {"query": {"type": "string"}}),
    "corporate_action_reference": (corporate_action_reference, {"query": {"type": "string"}}),
    "similar_cases": (similar_cases, {"query": {"type": "string"}}),
}

TOOL_SCHEMAS = [{"type": "function", "function": {
    "name": name, "description": fn.__doc__, "parameters": {"type": "object", "properties": props}}}
    for name, (fn, props) in TOOLS.items()]


def run_tool(name, args):
    if name not in TOOLS:
        return {"error": f"unknown tool {name}"}
    try:
        return TOOLS[name][0](**args)
    except TypeError as e:
        return {"error": str(e)}


# when to call it

def unusual_signals(case):
    """Reasons this case deserves a closer look. Empty for a routine case."""
    signals = []
    r, t = case.get("rca") or {}, case.get("triage") or {}
    if r and r["confidence"] < rca.confidence_threshold():
        signals.append(f"model confidence {r['confidence']:.2f} is below {rca.confidence_threshold():.2f}")
    if r and (r.get("document_finding") or {}).get("changed"):
        signals.append("the corporate action notice contradicted the model")
    if t and not t.get("family_agreement", {}).get("agrees", True):
        signals.append("Triage's family differs from the reconciliation engine's tag")
    return signals


# the loop

class InvestigatorState(TypedDict, total=False):
    messages: Annotated[list, operator.add]
    steps: Annotated[list, operator.add]
    rounds: int
    finding: str
    status: str


def think(state):
    final = state.get("rounds", 0) >= MAX_ROUNDS
    try:
        msg = llm.chat(state["messages"], system=SYSTEM, tools=None if final else TOOL_SCHEMAS,
                       max_tokens=700, timeout=30)
    except RuntimeError as e:
        return {"status": "MODEL_UNAVAILABLE", "finding": str(e)[:200]}
    msg = {"role": "assistant", "content": msg.get("content") or "", **(
        {"tool_calls": msg["tool_calls"]} if msg.get("tool_calls") and not final else {})}
    if "tool_calls" in msg:
        return {"messages": [msg], "rounds": state.get("rounds", 0) + 1}
    return {"messages": [msg], "finding": msg["content"].strip(), "status": "COMPLETE"}


def act(state):
    results, steps = [], []
    for call in state["messages"][-1]["tool_calls"]:
        name = call["function"]["name"]
        try:
            args = json.loads(call["function"].get("arguments") or "{}")
        except json.JSONDecodeError:
            args = {}
        result = run_tool(name, args)
        results.append({"role": "tool", "tool_call_id": call.get("id", name),
                        "content": json.dumps(result, default=str)[:MAX_RESULT_CHARS]})
        steps.append({"tool": name, "args": args,
                      "returned": len(result) if isinstance(result, list) else int(result is not None)})
    return {"messages": results, "steps": steps}


def after_think(state):
    return END if state.get("status") else "act"


def build():
    g = StateGraph(InvestigatorState)
    g.add_node("think", think)
    g.add_node("act", act)
    g.add_edge(START, "think")
    g.add_conditional_edges("think", after_think, ["act", END])
    g.add_edge("act", "think")
    return g.compile()


GRAPH = build()


def _brief(case, signals):
    ev, r, t = case["investigation"], case["rca"], case["triage"]
    trade = ev["structured_evidence"].get("trade") or {}
    return json.dumps({
        "break_id": case["break_id"], "break_type": ev["break_type"], "severity": ev["severity"],
        "reported": ev["reported"], "trade": {k: trade.get(k) for k in (
            "trade_id", "trade_date", "ticker", "isin", "quantity", "price", "counterparty", "settlement_date")},
        "triage_family": t["predicted_family"], "diagnosis": r["root_cause"],
        "confidence": round(r["confidence"], 3), "alternatives": r.get("alternative_explanations"),
        "unusual_signals": signals,
    }, default=str)


def investigate_further(case, signals=None):
    """Runs the loop for one case and returns what it found."""
    signals = signals if signals is not None else unusual_signals(case)
    if (os.environ.get("RESOLVIA_INVESTIGATOR", "on") == "off" or getattr(QUIET, "on", False)
            or not os.environ.get("OPENROUTER_API_KEY")):
        return {"signals": signals, "status": "NOT_RUN", "steps": [], "finding": ""}
    out = GRAPH.invoke({"messages": [{"role": "user", "content": _brief(case, signals)}], "rounds": 0})
    return {"signals": signals, "status": out.get("status", "COMPLETE"),
            "steps": out.get("steps", []), "finding": out.get("finding", "")}
