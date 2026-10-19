import unittest

import _setup
import control_gate
import orchestrator
from features import FEATURE_COLS, build_features
from investigation import investigate


class Pipeline(unittest.TestCase):
    def setUp(self):
        control_gate.reset()
        orchestrator.reset()

    def test_failed_payment_waits_then_closes(self):
        bid = _setup.first_break("SETL_WRONG_SSI")
        case = orchestrator.create_case(bid)
        self.assertEqual(case["status"], "AWAITING_APPROVAL")
        self.assertIsNone(case["post_execution"])
        control_gate.record_decision(bid, "APPROVE", "ops.lead", notes="SSI checked")
        self.assertEqual(orchestrator.resume_case(bid)["status"], "CLOSED")

    def test_rejected_case_never_executes(self):
        bid = _setup.first_break("CASH_WRONG_AMOUNT")
        orchestrator.create_case(bid)
        control_gate.record_decision(bid, "REJECT", "ops.lead")
        case = orchestrator.resume_case(bid)
        self.assertEqual(case["status"], "REJECTED")
        self.assertIsNone(case["post_execution"])

    def test_voluntary_corporate_action_is_held(self):
        bid = _setup.first_break("CA_VOLUNTARY_DECISION")
        case = orchestrator.create_case(bid)
        self.assertEqual(case["rca"]["root_cause"], "CA_VOLUNTARY_DECISION")
        self.assertTrue(case["rca"]["requires_human_decision"])
        control_gate.record_decision(bid, "APPROVE", "ca.desk")
        self.assertEqual(orchestrator.resume_case(bid)["status"], "ON_HOLD")

    def test_case_survives_a_restart(self):
        bid = _setup.first_break("SETL_WRONG_SSI")
        orchestrator.create_case(bid)
        orchestrator._CASES.clear()  # what a restart does to the cache
        case = orchestrator.get_case(bid)
        self.assertEqual(case["status"], "AWAITING_APPROVAL")
        self.assertIn("RCA_COMPLETE", [e["event"] for e in case["history"]])

    def test_pipeline_never_sees_the_answer(self):
        bundle = investigate(_setup.first_break("TRADE_PRICE_MISMATCH"))
        self.assertNotIn("mismatch_type", str(bundle.keys()))
        self.assertNotIn("root_cause", bundle)
        self.assertFalse({"family", "root_cause", "split", "break_id"} & set(FEATURE_COLS))

    def test_features_cover_every_break(self):
        self.assertEqual(len(build_features()), 3000)


if __name__ == "__main__":
    unittest.main()
