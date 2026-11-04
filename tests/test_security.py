import unittest

import _setup  # noqa: F401
import auth
import control_gate
import store


class SecurityControls(unittest.TestCase):
    def setUp(self):
        control_gate.reset()

    def test_api_style_decision_requires_distinct_authorized_approver(self):
        with self.assertRaises(ValueError):
            control_gate.record_decision("BRK_SEC", "APPROVE", "OPS-1047", actor_id="OPS-1047")

        saved = control_gate.record_decision("BRK_SEC", "APPROVE", "OPS-LEAD", actor_id="OPS-1047")
        self.assertEqual(saved["approver"], "OPS-LEAD")
        self.assertEqual(len(control_gate.decision_history("BRK_SEC")), 1)

    def test_unknown_identity_is_rejected(self):
        with self.assertRaises(PermissionError):
            auth.require_actor("not-a-real-operator")


if __name__ == "__main__":
    unittest.main()
