"""
Ingestion Agent: turns incoming documents into trade records.

Three ways in, all ending in the same trade schema:
  ingest_structured_row()   a CSV or API row, parsed directly
  ingest_text()             emails, notes and chat messages, read by an LLM
                            through a record_trades tool call
  ingest_scanned_image()    EasyOCR first, then the same LLM step
  ingest_text_rules()       regex and alias lookups only, the baseline the
                            LLM is measured against (eval/extraction_eval.py)

A batch email with several trades comes back as several records, not just
the first one found.

Not part of the break pipeline itself (that starts from the reconciliation
feed), but it's how new evidence would get in.
"""

import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "..", "data"))
import llm  # noqa: E402
from reference_data import COUNTERPARTIES, SYMBOL_ALIASES  # noqa: E402

COMMON_SCHEMA_FIELDS = ["trade_id", "symbol", "quantity", "price",
                          "counterparty", "side", "trade_date", "settlement_date"]

EXTRACTION_TOOL = {
  "type": "function",
  "function": {
    "name": "record_trades",
    "description": "Record the trade(s) found in a broker confirmation document.",
    "parameters": {
        "type": "object",
        "properties": {
            "trades": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "trade_id": {"type": ["string", "null"], "description": "Trade reference/ID if present"},
                        "symbol": {"type": ["string", "null"], "description": "Equity symbol, normalized to its NSE ticker if an alias/full name is used (e.g. 'Reliance Industries' -> 'RELIANCE')"},
                        "quantity": {"type": ["integer", "null"]},
                        "price": {"type": ["number", "null"]},
                        "counterparty": {"type": ["string", "null"], "description": "Broker/custodian code, e.g. HDFC-CUST"},
                        "side": {"type": ["string", "null"], "enum": ["BUY", "SELL", None]},
                        "settlement_date": {"type": ["string", "null"], "description": "ISO format YYYY-MM-DD"},
                    },
                    "required": ["trade_id", "symbol", "quantity", "price", "counterparty", "side", "settlement_date"],
                },
            },
        },
        "required": ["trades"],
    },
  },
}

EXTRACTION_SYSTEM_PROMPT = """You extract structured trade data from broker/custodian confirmation \
documents for a trade reconciliation system. Documents may be formal emails, terse system \
notes, informal chat/WhatsApp-style messages, OCR output from a scanned PDF (which may contain \
minor character errors), or a single email covering multiple trades. Extract every trade found; \
a batch email with several trades must produce one entry per trade, not just the first. \
Normalize symbol aliases and company names to their ticker (RELIANCE, TCS, INFY, HDFCBANK, \
ICICIBANK, SBIN, BHARTIARTL, ITC, LT, AXISBANK, KOTAKBANK, WIPRO, HINDUNILVR, MARUTI, TATASTEEL). \
Normalize all dates to YYYY-MM-DD. If a field isn't in the document in the document, use null \
rather than guessing. Call record_trades with your findings."""


def ingest_structured_row(row):
    """A row that's already structured just needs its types fixing."""
    return {
        "trade_id": row["trade_id"],
        "symbol": row["symbol"],
        "quantity": int(row["quantity"]),
        "price": float(row["price"]),
        "counterparty": row["counterparty"],
        "side": row.get("side"),
        "trade_date": row.get("trade_date"),
        "settlement_date": row["settlement_date"],
        "source": "structured_feed",
        "extraction_method": "deterministic",
    }


# A rules-only reader for the same documents, as a baseline for the LLM.

_DATE = r"(\d{4}-\d{2}-\d{2}|\d{2}[-/]\d{2}[-/]\d{4})"
_NUM = r"(\d[\d,]*\.?\d*)"
_ALIASES = sorted(((alias.upper(), ticker) for ticker, names in SYMBOL_ALIASES.items() for alias in names),
                  key=lambda x: -len(x[0]))
_DOMAIN_TO_CP = {cp.split("-")[0].lower(): cp for cp in COUNTERPARTIES}


def _iso(date):
    if re.fullmatch(r"\d{8}", date):
        return f"{date[:4]}-{date[4:6]}-{date[6:]}"
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return date
    d, m, y = re.split(r"[-/]", date)
    return f"{y}-{m}-{d}"


def _first(patterns, text):
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            return m.group(1)
    return None


def _read_fields(segment, whole):
    u, w = segment.upper(), whole.upper()
    qty = _first([r"\bQTY\s*:?\s*" + _NUM, r"\bQUANTITY\s*:?\s*" + _NUM,
                  r"\b(?:BUY|SELL)\s+" + _NUM + r"\s*@", r"UNIT/" + _NUM], u)
    price = _first([r"@\s*(?:INR|RS\.?)?\s*" + _NUM, r"\b(?:PRICE|RATE)\s*:?\s*(?:INR|RS\.?)?\s*" + _NUM,
                    r"\bAROUND\s+" + _NUM], u)
    date = _first([r"\b(?:SETTLEMENT(?:\s+SHOULD\s+BE)?|SD|VALUE\s+DATE)\s*:?\s*" + _DATE,
                   r"SETT-(\d{8})", r"SETT//(\d{8})"], u) or _first([r"SETT-(\d{8})"], w)
    side = _first([r"\b(BUY|SELL)\b"], u)
    symbol = next((t for alias, t in _ALIASES if re.search(rf"(?<![A-Z]){re.escape(alias)}(?![A-Z])", u)), None)
    cp = _first([r"\b(" + "|".join(COUNTERPARTIES) + r")\b"], u) or _first([r"\b(" + "|".join(COUNTERPARTIES) + r")\b"], w)
    if cp is None:
        m = re.search(r"@([a-z]+)\.com", whole)
        cp = _DOMAIN_TO_CP.get(m.group(1)) if m else None
    return {
        "symbol": symbol, "side": side, "counterparty": cp,
        "quantity": int(qty.replace(",", "")) if qty else None,
        "price": float(price.replace(",", "").rstrip(".")) if price else None,
        "settlement_date": _iso(date) if date else None,
    }


def ingest_text_rules(text, doc_id=None):
    """Regex and alias lookups only, no model. One record per trade reference."""
    ids = list(dict.fromkeys(re.findall(r"TRD\d{6}", text)))
    lines = text.splitlines()
    trades = []
    for tid in ids:
        segment = text if len(ids) == 1 else next(l for l in lines if tid in l)
        trades.append(dict(_read_fields(segment, text), trade_id=tid,
                           source=f"unstructured_text:{doc_id}" if doc_id else "unstructured_text",
                           extraction_method="rules"))
    return trades


def _parse_trades(message):
    """Pull the trade list out of a chat reply (tool call, or JSON in plain text)."""
    calls = message.get("tool_calls")
    try:
        if calls:
            return json.loads(calls[0]["function"]["arguments"]).get("trades", [])
        content = message.get("content") or ""
        parsed = json.loads(content[content.find("{"):content.rfind("}") + 1])
        return parsed.get("trades", []) if isinstance(parsed, dict) else parsed
    except (ValueError, AttributeError):
        return []


def ingest_text(text, doc_id=None):
    """Reads trades out of any text document. Usually one trade, more for a batch email."""
    trades = []
    for model in llm.model_list():  # free models are flaky; move on if one returns nothing
        try:
            message = llm.chat(
                [{"role": "user", "content": text}],
                system=EXTRACTION_SYSTEM_PROMPT,
                tools=[EXTRACTION_TOOL],
                tool_choice={"type": "function", "function": {"name": "record_trades"}},
                model=model,
            )
        except RuntimeError:
            continue
        trades = _parse_trades(message)
        if trades:
            break
    for t in trades:
        t["source"] = f"unstructured_text:{doc_id}" if doc_id else "unstructured_text"
        t["extraction_method"] = "llm_text"
    return trades


def ingest_scanned_image(image_path, doc_id=None, reader=None):
    """OCR the image, then read the text like any other document."""
    if reader is None:
        import easyocr
        # verbose=False: EasyOCR's progress bar crashes a default Windows console
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)

    lines = reader.readtext(image_path, detail=0)
    ocr_text = "\n".join(lines)

    trades = ingest_text(ocr_text, doc_id=doc_id)
    for t in trades:
        t["extraction_method"] = "llm_ocr"
        t["ocr_text"] = ocr_text
    return trades


if __name__ == "__main__":
    import csv
    import sys

    print("=== Structured ingestion (deterministic, no model) ===")
    with open("../../data/trades.csv", newline="") as f:
        rows = list(csv.DictReader(f))
    for row in rows[:3]:
        row = dict(row, symbol=row["security"])  # trades.csv calls it security
        print(json.dumps(ingest_structured_row(row), indent=2))

    if "--skip-llm" in sys.argv:
        print("\n(--skip-llm passed, not calling the LLM)")
        sys.exit(0)

    print("\n=== Text ingestion (LLM extraction) ===")
    doc_path = "../../data/broker_confirms/doc_0001.txt"
    with open(doc_path, encoding="utf-8") as f:
        text = f.read()
    try:
        print(json.dumps(ingest_text(text, doc_id="doc_0001"), indent=2))
    except Exception as e:
        print(f"LLM extraction not run: {e}")
