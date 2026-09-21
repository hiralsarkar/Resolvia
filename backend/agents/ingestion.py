"""
Ingestion Agent.

Three paths into the same common trade schema:
  - ingest_structured_row()   deterministic CSV/API parsing (no model)
  - ingest_text()             LLM extraction (tool-call/JSON
                               schema output) for text-based emails,
                               notes, WhatsApp-style messages
  - ingest_scanned_image()    EasyOCR (frozen, pretrained) -> the same
                               ingest_text() LLM extraction step

A multi-trade batch email extracts to a LIST of records, not one -
the schema and both LLM paths handle that explicitly rather than
silently keeping only the first trade found.
"""

import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import llm  # noqa: E402

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
minor character errors), or a single email covering multiple trades. Extract every trade found \
- a batch email with several trades must produce one entry per trade, not just the first. \
Normalize symbol aliases and company names to their ticker (RELIANCE, TCS, INFY, HDFCBANK, \
ICICIBANK, SBIN, BHARTIARTL, ITC, LT, AXISBANK, KOTAKBANK, WIPRO, HINDUNILVR, MARUTI, TATASTEEL). \
Normalize all dates to YYYY-MM-DD. If a field genuinely isn't present in the document, use null \
rather than guessing. Call record_trades with your findings."""


def ingest_structured_row(row):
    """Deterministic passthrough for an already-structured CSV/API row -
    no model involved."""
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
    """LLM extraction for any text-based document (email, terse note,
    chat-style, or already-OCR'd scanned document). Returns a list of
    trade dicts (usually length 1, more for a batch email)."""
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
    """OCR (EasyOCR, frozen pretrained) -> ingest_text() on the result."""
    if reader is None:
        import easyocr
        # verbose=False - EasyOCR's download progress bar prints a Unicode
        # block character that crashes under Windows' default cp1252
        # console codepage (hit this directly during testing).
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
        row = dict(row, symbol=row["security"])  # trades.csv column is `security`, not `symbol`
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
