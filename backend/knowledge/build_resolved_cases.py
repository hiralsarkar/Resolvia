"""
build_resolved_cases.py 

Seeds the resolved_cases precedent corpus by running a stratified sample
of breaks through the real Orchestrator (create_case/resume_case - the
same production entry points the Streamlit app uses, CONTROLLED_ACTION
cases auto-approved here to simulate a completed approval history, not
to bypass governance). Both proposal PDFs promise precedent-RAG; nothing
implemented it until now because no case had ever been closed through
the pipeline. It has, now - 20/20 root-cause coverage runs (see
orchestrator.py's own smoke test) proved the mechanism works.

Up to CASES_PER_ROOT_CAUSE closed/reopened cases per root cause (not all
3000 breaks - a precedent corpus needs representative diversity per
cause, not volume; keeping this bounded also keeps seeding runtime
reasonable). Prioritizes breaks with document evidence, since those
produce the most useful evidence_cited precedent text.

Output:
  backend/knowledge/resolved_cases.json
  backend/embeddings/saved/resolved_cases_index.* (via build_indices.py)
"""

import json
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "agents"))
sys.path.insert(0, os.path.join(HERE, ".."))

import control_gate  # noqa: E402
import orchestrator  # noqa: E402
from investigation import _tables  # noqa: E402

CASES_PER_ROOT_CAUSE = 20


def _select_sample():
    breaks = _tables()["breaks"]
    by_cause = defaultdict(list)
    for bid, b in breaks.items():
        by_cause[b["mismatch_type"]].append((bid, b))
    sample = []
    for rc, rows in by_cause.items():
        rows.sort(key=lambda x: x[1]["needs_evidence_bundle"] != "True")  # evidence-bundle rows first
        sample.extend(rows[:CASES_PER_ROOT_CAUSE])
    return sample


def _precedent_text(case):
    parts = [case["break_id"], case["root_cause_desc"], case["family"], case["severity"],
              f"action: {case['recommended_action']}", f"outcome: {case['final_status']}"]
    if case["evidence_cited"]:
        parts.append("evidence: " + "; ".join(case["evidence_cited"]))
    return " | ".join(str(p) for p in parts if p)


def main():
    control_gate.reset()
    orchestrator.reset()
    sample = _select_sample()

    resolved = []
    for bid, b in sample:
        case = orchestrator.create_case(bid)
        if case["status"] == "AWAITING_APPROVAL":
            control_gate.record_decision(bid, "APPROVE", "precedent.seed@resolvia.local",
                                          notes="offline seeding run - simulated approval history")
            case = orchestrator.resume_case(bid)
        if case["status"] not in ("CLOSED", "REOPENED"):
            continue  # skip REJECTED/HALTED - not useful as resolution precedent

        proposal = case["proposal"]
        resolved.append({
            "break_id": bid,
            "root_cause": b["mismatch_type"],
            "root_cause_desc": b["root_cause"],
            "family": b["break_type"],
            "severity": b["severity"],
            "corporate_action_type": b["corporate_action_type"],
            "recommended_action": proposal["recommended_action"],
            "authority_tier": proposal["authority_tier"],
            "rca_confidence": proposal["rca_confidence"],
            "evidence_cited": proposal["evidence_cited"],
            "final_status": case["status"],
            "validation_reason": case["validation"]["reason"],
        })

    out_path = os.path.join(HERE, "resolved_cases.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2)

    print(f"Seeded {len(resolved)} resolved cases across {len(set(r['root_cause'] for r in resolved))} root causes")
    print(f"-> {out_path}")
    from collections import Counter
    print("By final_status:", dict(Counter(r["final_status"] for r in resolved)))


if __name__ == "__main__":
    main()
