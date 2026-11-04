import unittest

import _setup  # noqa: F401
import state_machine


class StateMachine(unittest.TestCase):
    def test_valid_manual_path(self):
        state_machine.require_transition("IN_REVIEW", "MANUAL_IN_PROGRESS")
        state_machine.require_transition("MANUAL_IN_PROGRESS", "AWAITING_VERIFICATION")
        state_machine.require_transition("AWAITING_VERIFICATION", "CLOSED")

    def test_direct_close_is_blocked(self):
        with self.assertRaises(ValueError):
            state_machine.require_transition("IN_REVIEW", "CLOSED")

    def test_closed_is_terminal(self):
        with self.assertRaises(ValueError):
            state_machine.require_transition("CLOSED", "IN_REVIEW")


if __name__ == "__main__":
    unittest.main()
