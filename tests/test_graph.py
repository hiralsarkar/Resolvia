import json
import os
import unittest
from unittest import mock

import _setup
import control_gate
import investigator
import orchestrator


def scripted_llm(*replies):
    """Stands in for the language model: returns the given messages in order."""
    replies = list(replies)
    return mock.patch.object(investigator.llm, "chat", side_effect=lambda *a, **k: replies.pop(0))


def tool_call(name, **args):
    return {"role": "assistant", "content": "", "tool_calls": [
        {"id": f"call_{name}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


class Graph(unittest.TestCase):
    def setUp(self):
        control_gate.reset()
        orchestrator.reset()

    def test_graph_has_every_stage(self):
        nodes = set(orchestrator.GRAPH.get_graph().nodes)
        for n in ("triage", "investigate", "rca", "investigator", "propose", "gate",
                  "await_approval", "execute", "validate"):
            self.assertIn(n, nodes)
        self.assertIn("investigator", orchestrator.mermaid())

    def test_routine_case_skips_the_investigator(self):
        case = orchestrator.create_case(_setup.first_break("SETL_WRONG_SSI"))
        self.assertIsNone(case["further_investigation"])

    def test_pause_keeps_what_the_app_added(self):
        bid = _setup.first_break("SETL_WRONG_SSI")
        case = orchestrator.create_case(bid)
        orchestrator._log(case, "EXECUTION_MODE", "Controlled Action")
        orchestrator.save(case)
        control_gate.record_decision(bid, "APPROVE", "ops.lead")
        events = [e["event"] for e in orchestrator.resume_case(bid)["history"]]
        self.assertEqual(events.count("EXECUTION_MODE"), 1)
        self.assertLess(events.index("EXECUTION_MODE"), events.index("EXECUTION_COMPLETE"))
        self.assertEqual(events[-1], "CASE_CLOSED")

    def test_unusual_case_is_investigated_then_goes_to_a_person(self):
        bid = _setup.first_break("TRADE_PRICE_MISMATCH")
        env = {"RESOLVIA_INVESTIGATOR": "on", "OPENROUTER_API_KEY": "test"}
        with mock.patch.dict(os.environ, env), \
                mock.patch.object(investigator, "unusual_signals", return_value=["test signal"]), \
                scripted_llm(tool_call("find_trades", ticker="RELIANCE"),
                             tool_call("similar_cases", query="price differs from the broker"),
                             {"role": "assistant", "content": "Broker confirmed a different price."}):
            case = orchestrator.create_case(bid)

        f = case["further_investigation"]
        self.assertEqual(f["status"], "COMPLETE")
        self.assertEqual([s["tool"] for s in f["steps"]], ["find_trades", "similar_cases"])
        self.assertEqual(f["finding"], "Broker confirmed a different price.")
        self.assertTrue(case["proposal"]["approval_required"])
        self.assertEqual(case["status"], "AWAITING_APPROVAL")
        events = [e["event"] for e in case["history"]]
        self.assertLess(events.index("RCA_COMPLETE"), events.index("FURTHER_INVESTIGATION"))
        self.assertIn("INVESTIGATOR_FINDING", events)

    def test_investigator_concludes_within_its_budget(self):
        case = orchestrator.create_case(_setup.first_break("CASH_WRONG_AMOUNT"))
        endless = [tool_call("cash_entries", trade_id="TRD100000")] * investigator.MAX_ROUNDS
        env = {"RESOLVIA_INVESTIGATOR": "on", "OPENROUTER_API_KEY": "test"}
        with mock.patch.dict(os.environ, env), \
                scripted_llm(*endless, {"role": "assistant", "content": "Done."}):
            f = investigator.investigate_further(case, ["test signal"])
        self.assertEqual(len(f["steps"]), investigator.MAX_ROUNDS)
        self.assertEqual(f["finding"], "Done.")


if __name__ == "__main__":
    unittest.main()
