import unittest

import _setup  # noqa: F401
import control_gate as gate


def proposal(tier="CONTROLLED_ACTION", approval=True, break_id="BRK_T1"):
    return {"break_id": break_id, "authority_tier": tier, "approval_required": approval}


class ControlGate(unittest.TestCase):
    def setUp(self):
        gate.reset()

    def test_admin_step_on_unflagged_diagnosis_passes(self):
        self.assertTrue(gate.check_gate(proposal("PROPOSAL", approval=False))["authorized"])

    def test_controlled_action_waits_for_a_person(self):
        self.assertFalse(gate.check_gate(proposal())["authorized"])
        gate.record_decision("BRK_T1", "APPROVE", "ops.lead")
        self.assertTrue(gate.check_gate(proposal())["authorized"])

    def test_reject_blocks(self):
        gate.record_decision("BRK_T1", "REJECT", "ops.lead", notes="need the statement")
        result = gate.check_gate(proposal())
        self.assertFalse(result["authorized"])
        self.assertIn("rejected", result["reason"])

    def test_flagged_diagnosis_needs_approval_even_for_admin_steps(self):
        self.assertFalse(gate.check_gate(proposal("PROPOSAL", approval=True))["authorized"])

    def test_only_approve_or_reject(self):
        with self.assertRaises(ValueError):
            gate.record_decision("BRK_T1", "MAYBE", "ops.lead")

    def test_every_check_and_decision_is_logged(self):
        gate.check_gate(proposal())
        gate.record_decision("BRK_T1", "APPROVE", "ops.lead")
        gate.check_gate(proposal())
        events = [e["event"] for e in gate.audit_trail("BRK_T1")]
        self.assertEqual(events, ["GATE_CHECK:BLOCKED", "HUMAN_DECISION:APPROVE", "GATE_CHECK:AUTHORIZED"])


if __name__ == "__main__":
    unittest.main()
