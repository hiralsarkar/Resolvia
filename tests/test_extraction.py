import csv
import os
import unittest

import _setup
from ingestion import ingest_text_rules


def docs(template):
    with open(os.path.join(_setup.ROOT, "data", "broker_confirms_mapping.csv"), newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["template_used"] == template]
    return rows


class RulesExtractor(unittest.TestCase):
    def test_formal_email(self):
        row = docs("template_formal_email")[0]
        got = ingest_text_rules(_setup.document(row["doc_id"]))[0]
        self.assertEqual(got["trade_id"], row["trade_id"])
        self.assertEqual(got["symbol"], row["symbol"])
        self.assertEqual(got["quantity"], int(row["quantity"]))
        self.assertAlmostEqual(got["price"], float(row["price"]), places=2)

    def test_batch_email_gives_one_record_per_trade(self):
        rows = docs("template_batch_email")
        doc_id = rows[0]["doc_id"]
        expected = {r["trade_id"] for r in rows if r["doc_id"] == doc_id}
        got = {t["trade_id"] for t in ingest_text_rules(_setup.document(doc_id))}
        self.assertEqual(got, expected)


if __name__ == "__main__":
    unittest.main()
