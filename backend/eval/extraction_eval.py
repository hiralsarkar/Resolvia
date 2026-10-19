"""
How well can trade details be read out of free-text documents?

Ground truth is broker_confirms_mapping.csv: for every document I know which
trade it covers and the values it was written with. Each extractor reads the
documents and is scored field by field: trade reference found, symbol,
quantity, price, counterparty and settlement date.

Extractors:
  rules   regex and alias lookups (agents/ingestion.py), no model
  llm     the LLM extraction step; needs OPENROUTER_API_KEY. --limit keeps
          the run small enough for free-tier models
  --ocr   also runs EasyOCR on the scanned images first, then the extractor
  --noise adds OCR-style character errors to the text, to see which
          extractor copes with a bad scan

Documents covered: the six kinds of ops correspondence (emails, notes, chat,
WhatsApp, scanned-style advices, batch emails) and the contract notes. SWIFT
settlement messages and corporate action notices aren't trade confirmations
and are tested elsewhere.

Run from backend/:  python eval/extraction_eval.py [--llm] [--ocr] [--noise 0.05] [--limit N]
Results for each method are merged into docs/analysis/extraction.json and .md
"""

import argparse
import csv
import json
import os
import random
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "agents"))
DATA_DIR = os.path.join(HERE, "..", "..", "data")
OUT = os.path.join(HERE, "..", "..", "docs", "analysis", "extraction")

sys.path.insert(0, DATA_DIR)
import ingestion  # noqa: E402
from perturb import ocr_noise  # noqa: E402

TEMPLATES = {
    "template_formal_email": "formal email", "template_terse_note": "terse note",
    "template_informal_chat_style": "chat message", "template_whatsapp_style": "WhatsApp",
    "template_scanned_pdf_style": "scanned-style advice", "template_batch_email": "batch email",
    "template_contract_note": "contract note",
}
FIELDS = ["trade_id", "symbol", "quantity", "price", "counterparty", "settlement_date"]


def ground_truth():
    """What each document actually says. The mapping holds the booked trade;
    a contract note shows the counterparty's confirmed quantity and price,
    which is the whole point of a trade break, so those come from trades.csv."""
    with open(os.path.join(DATA_DIR, "trades.csv"), newline="") as f:
        trades = {r["trade_id"]: r for r in csv.DictReader(f)}
    docs = defaultdict(list)
    with open(os.path.join(DATA_DIR, "broker_confirms_mapping.csv"), newline="") as f:
        for r in csv.DictReader(f):
            if r["template_used"] not in TEMPLATES:
                continue
            if r["template_used"] == "template_contract_note":
                t = trades[r["trade_id"]]
                r = dict(r, quantity=t["confirmed_quantity"] or t["quantity"],
                         price=t["confirmed_price"] or t["price"])
            docs[r["doc_id"]].append(r)
    return docs


def field_ok(field, truth, got):
    if got is None:
        return False
    if field == "quantity":
        return int(float(truth[field])) == int(got)
    if field == "price":
        return abs(float(truth[field]) - float(got)) < 0.005
    return str(truth[field]).upper() == str(got).upper()


def score(docs, extract):
    per = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for doc_id, rows in docs.items():
        text = extract.text(doc_id)
        try:
            found = {t.get("trade_id"): t for t in extract(text, doc_id) if t.get("trade_id")}
        except Exception as e:  # a failed call counts as nothing found
            print(f"{doc_id}: {e}")
            found = {}
        kind = TEMPLATES[rows[0]["template_used"]]
        for truth in rows:
            got = found.get(truth["trade_id"], {})
            for field in FIELDS:
                ok = field == "trade_id" and bool(got) or field != "trade_id" and field_ok(field, truth, got.get(field))
                for key in (kind, "all"):
                    per[key][field][0] += ok
                    per[key][field][1] += 1
    return {k: {f: round(c[0] / c[1], 3) for f, c in v.items()} | {"n": v["trade_id"][1]} for k, v in per.items()}


class Extractor:
    def __init__(self, fn, ocr=False, noise=0.0):
        self.fn, self.ocr, self.noise, self.reader = fn, ocr, noise, None

    def text(self, doc_id):
        if self.ocr:
            if self.reader is None:
                import easyocr
                self.reader = easyocr.Reader(["en"], gpu=False, verbose=False)
            return "\n".join(self.reader.readtext(os.path.join(DATA_DIR, "scanned_images", f"{doc_id}.jpg"), detail=0))
        with open(os.path.join(DATA_DIR, "broker_confirms", f"{doc_id}.txt"), encoding="utf-8") as f:
            return ocr_noise(f.read(), self.noise, seed=int(doc_id[4:]))

    def __call__(self, text, doc_id):
        return self.fn(text, doc_id)


def write(results):
    md = ["# Document extraction\n",
          "Written by `backend/eval/extraction_eval.py`. Share of trades where each field was read correctly. "
          "Ground truth is `data/broker_confirms_mapping.csv`.\n"]
    for method, res in results.items():
        md.append(f"## {method}\n")
        md.append("| document kind | trades | " + " | ".join(FIELDS) + " |")
        md.append("|---|---|" + "---|" * len(FIELDS))
        for kind in [*TEMPLATES.values(), "all"]:
            if kind in res:
                md.append(f"| {kind} | {res[kind]['n']} | " + " | ".join(f"{res[kind][f]:.0%}" for f in FIELDS) + " |")
        md.append("")
    if not any(m.startswith("llm") for m in results):
        md.append("The LLM column appears once the script is run with `--llm` and an OpenRouter key.\n")
    with open(OUT + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(md))
    with open(OUT + ".json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--ocr", action="store_true")
    ap.add_argument("--limit", type=int, default=None, help="score a random sample of documents")
    ap.add_argument("--noise", type=float, default=0.0, help="OCR-style character error rate added to the text")
    args = ap.parse_args()

    docs = ground_truth()
    if args.ocr:
        scans = {f[:-4] for f in os.listdir(os.path.join(DATA_DIR, "scanned_images"))}
        docs = {d: r for d, r in docs.items() if d in scans}
    if args.limit and args.limit < len(docs):
        docs = dict(random.Random(0).sample(sorted(docs.items()), args.limit))

    results = {}
    if os.path.exists(OUT + ".json"):
        with open(OUT + ".json", encoding="utf-8") as f:
            results = json.load(f)

    suffix = " (after OCR)" if args.ocr else (f" ({args.noise:.0%} character noise)" if args.noise else "")
    if args.limit:
        suffix += f", {len(docs)} documents"
    fn = (lambda t, d: ingestion.ingest_text(t, doc_id=d)) if args.llm else \
        (lambda t, d: ingestion.ingest_text_rules(t, doc_id=d))
    results[("llm" if args.llm else "rules") + suffix] = score(docs, Extractor(fn, args.ocr, args.noise))
    write(results)
    print(open(OUT + ".md", encoding="utf-8").read())


if __name__ == "__main__":
    main()
