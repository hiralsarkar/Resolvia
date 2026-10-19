import unittest

import _setup
import execution_simulator as sim
from investigation import investigate, break_feed
from validation import validate


class Validation(unittest.TestCase):
    def setUp(self):
        self.bid = _setup.first_break("SETL_WRONG_SSI")
        self.evidence, self.feed = investigate(self.bid), break_feed(self.bid)

    def run_fix(self, cause, kind="CORRECT"):
        proposal = {"root_cause": cause, "action_kind": kind}
        return validate(self.bid, self.feed, sim.execute(proposal, self.evidence, self.feed), proposal)

    def test_right_fix_closes(self):
        self.assertEqual(self.run_fix("SETL_WRONG_SSI")["status"], "CLOSED")

    def test_wrong_fix_reopens(self):
        self.assertEqual(self.run_fix("SETL_INCORRECT_DATE")["status"], "REOPENED")

    def test_nothing_ran_stays_open(self):
        self.assertEqual(validate(self.bid, self.feed, None)["status"], "OPEN")

    def test_hold_is_not_a_failure(self):
        self.assertEqual(self.run_fix("CA_VOLUNTARY_DECISION", "HOLD")["status"], "ON_HOLD")

    def test_source_records_are_never_changed(self):
        before = dict(self.evidence["structured_evidence"]["settlement"])
        self.run_fix("SETL_WRONG_SSI")
        self.assertEqual(self.evidence["structured_evidence"]["settlement"], before)


if __name__ == "__main__":
    unittest.main()
