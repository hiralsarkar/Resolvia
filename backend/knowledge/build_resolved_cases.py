"""
Builds the precedent corpus: a set of past cases the RCA agent can look back on.

I take up to 20 breaks per root cause (ones with documents first, since they
give richer evidence) and run them through the real Orchestrator, the same
entry points the app uses. Anything that needs approval is approved here to
stand in for an approval history. Once a case is resolved its root cause is
known, so the corpus records the true cause, the action taken and how it
ended.

Output: backend/knowledge/resolved_cases.json
Then run backend/embeddings/build_indices.py to rebuild the search index.
"""

import json
import os
import sys
from collections import Counter, defaultdict


# batch runs use a throwaway database, never the real audit trail
os.environ.setdefault("RESOLVIA_DB", ":memory:")
os.environ.setdefault("RESOLVIA_INVESTIGATOR", "off")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "agents"))
sys.path.insert(0, os.path.join(HERE, ".."))

import control_gate  # noqa: E402
import orchestrator  # noqa: E402
from investigation import _tables  # noqa: E402

CASES_PER_ROOT_CAUSE = 20
KEEP_STATUSES = ("CLOSED", "REOPENED", "ON_HOLD")


def _select_sample():
    by_cause = defaultdict(list)
    for bid, b in _tables()["breaks"].items():
        by_cause[b["mismatch_type"]].append((bid, b))
    sample = []
    for rows in by_cause.values():
        rows.sort(key=lambda x: x[1]["needs_evidence_bundle"] != "True")
        sample.extend(rows[:CASES_PER_ROOT_CAUSE])
    return sample


def main():
    control_gate.reset()
    orchestrator.reset()

    resolved = []
    for bid, b in _select_sample():
        case = orchestrator.create_case(bid)
        if case["status"] == "AWAITING_APPROVAL":
            control_gate.record_decision(bid, "APPROVE", "precedent.seed@resolvia.local",
                                         notes="seeding run, stands in for approval history")
            case = orchestrator.resume_case(bid)
        if case["status"] not in KEEP_STATUSES:
            continue

        p = case["proposal"]
        resolved.append({
            "break_id": bid,
            "root_cause": b["mismatch_type"],
            "root_cause_desc": b["root_cause"],
            "family": b["break_type"],
            "severity": b["severity"],
            "corporate_action_type": b["corporate_action_type"],
            "recommended_action": p["recommended_action"],
            "authority_tier": p["authority_tier"],
            "rca_confidence": p["rca_confidence"],
            # a precedent shouldn't cite other precedents
            "evidence_cited": [e for e in p["evidence_cited"] if not e.startswith("precedent:")],
            "final_status": case["status"],
            "validation_reason": case["validation"]["reason"],
        })

    out_path = os.path.join(HERE, "resolved_cases.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(resolved, f, indent=2)

    print(f"{len(resolved)} cases across {len({r['root_cause'] for r in resolved})} root causes -> {out_path}")
    print("by outcome:", dict(Counter(r["final_status"] for r in resolved)))


if __name__ == "__main__":
    main()
