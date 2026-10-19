import csv
import os
import unittest

import _setup
from perturb import ocr_noise
from rca import read_ca_notice


def notices():
    with open(os.path.join(_setup.ROOT, "data", "broker_confirms_mapping.csv"), newline="") as f:
        return [(r["doc_id"], r["corporate_action_type"]) for r in csv.DictReader(f) if r["corporate_action_type"]]


class NoticeParser(unittest.TestCase):
    def test_reads_every_clean_notice(self):
        for doc_id, ca_type in notices():
            n = read_ca_notice(_setup.document(doc_id))
            self.assertIsNotNone(n, doc_id)
            self.assertEqual(n["election_required"], ca_type == "VOLUNTARY", doc_id)

    def test_survives_a_slightly_damaged_scan(self):
        ok = sum(read_ca_notice(ocr_noise(_setup.document(d), 0.05, seed=1)) is not None for d, _ in notices())
        self.assertGreater(ok / len(notices()), 0.95)

    def test_conflicting_signals_are_not_trusted(self):
        text = ":22F::CAEV//TEND\n:22F::CAMV//MAND\n:70E::ADTX//ELECTION REQUIRED BY 09/08/2026"
        self.assertIsNone(read_ca_notice(text))

    def test_not_a_notice(self):
        self.assertIsNone(read_ca_notice("hi team, confirming the buy of TCS qty 500"))
        self.assertIsNone(read_ca_notice(None))


if __name__ == "__main__":
    unittest.main()
