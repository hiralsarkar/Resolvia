"""
generate_broker_confirms.py 

Generates evidence documents for breaks flagged `needs_evidence_bundle=True`
in breaks.csv (see generate_trade_breaks.py's per-family evidence rule:
100% of CA/SETTLEMENT/TRADE breaks, ~25% sample of POSITION-non-CA/CASH).

Documents are grounded document format in real messaging/document
standards researched for this project, routed by break family so each
document type is generated where it's the authentic real-world artifact:
  - CA breaks              -> SWIFT MT564-style corporate action notice
                               (ISO 15022: CAMV mandatory/voluntary field,
                               NOAC default option code for voluntary events)
  - SETTLEMENT-family       -> SWIFT MT54x-style settlement instruction/
                               status message (:16R:/:16S: block syntax,
                               :20C:/:35B:/:36B:/:98A:/:95Q: field tags)
  - TRADE-family            -> NSE/SEBI-style contract note (UCC, SEBI reg
                               no., STT/GST/stamp duty breakdown)
  - POSITION (non-CA), CASH -> original plain-English ops templates
                               (email/note/chat/scanned/whatsapp/batch) -
                               no equivalent standardized real-world format
                               exists for internal position/cash breaks;
                               these are legitimately ops correspondence.

Every generated document is clearly synthetic by construction: fake BICs/
SEBI registration numbers/client codes, an internal demo counterparty
list - never formatted to be mistakable for a genuine institutional
record. For TRADE-family breaks, the document reflects the external/
confirmed view (trades.confirmed_* columns) - i.e. what the counterparty
actually sent, which disagrees with the booking on purpose. For every
other family, the document reflects the booked trade (the trade itself
isn't what's wrong - the position/cash/settlement record is).

Output:
  broker_confirms/doc_0001.txt ... doc_0NNN.txt
  broker_confirms_mapping.csv  (doc_id -> break_id -> ground truth)
"""

import csv
import random
import os
from fractions import Fraction

random.seed(7)

SYMBOL_ALIASES = {
    "RELIANCE": ["RELIANCE", "RIL", "Reliance Industries"],
    "TCS": ["TCS", "Tata Consultancy Services", "Tata Consultancy"],
    "INFY": ["INFY", "Infosys", "Infosys Ltd"],
    "HDFCBANK": ["HDFCBANK", "HDFC Bank"],
    "ICICIBANK": ["ICICIBANK", "ICICI Bank"],
    "SBIN": ["SBIN", "SBI", "State Bank of India"],
    "BHARTIARTL": ["BHARTIARTL", "Bharti Airtel", "Airtel"],
    "ITC": ["ITC", "ITC Ltd"],
    "LT": ["LT", "L&T", "Larsen & Toubro"],
    "AXISBANK": ["AXISBANK", "Axis Bank"],
    "KOTAKBANK": ["KOTAKBANK", "Kotak Bank", "Kotak Mahindra Bank"],
    "WIPRO": ["WIPRO", "Wipro Ltd"],
    "HINDUNILVR": ["HINDUNILVR", "HUL", "Hindustan Unilever"],
    "MARUTI": ["MARUTI", "Maruti Suzuki"],
    "TATASTEEL": ["TATASTEEL", "Tata Steel"],
}

CONTACT_NAMES = ["R. Menon", "S. Kapoor", "A. Fernandes", "N. Rao",
                  "P. Iyer", "K. Sharma", "V. Desai"]


def fmt_date(d):
    """Occasionally reformat date to add noise (DD-MM-YYYY vs YYYY-MM-DD)."""
    y, m, dd = d.split("-")
    return random.choice([d, f"{dd}-{m}-{y}", f"{dd}/{m}/{y}"])


def template_formal_email(row, contact):
    symbol = random.choice(SYMBOL_ALIASES.get(row["symbol"], [row["symbol"]]))
    return f"""From: {contact} <{contact.split('.')[0].lower()}@{row['counterparty'].split('-')[0].lower()}.com>
To: ops-recon@ourfirm.com
Subject: Trade Confirmation - {row['trade_id']}

Dear Team,

Please find below confirmation for the following trade executed on {fmt_date(row['trade_date'])}:

  Security     : {symbol}
  Txn Type     : {row['side']}
  Qty          : {row['quantity']}
  Price        : INR {row['price']}
  Settlement   : {fmt_date(row['settlement_date'])}
  Our Ref      : {row['trade_id']}

Kindly confirm receipt and advise if any discrepancy at your end.

Regards,
{contact}
{row['counterparty']}
"""


def template_terse_note(row, contact):
    symbol = random.choice(SYMBOL_ALIASES.get(row["symbol"], [row["symbol"]]))
    return f"""CONFIRMATION NOTE
Ref: {row['trade_id']}
{symbol} | {row['side']} {row['quantity']} @ {row['price']}
SD: {fmt_date(row['settlement_date'])}
CP: {row['counterparty']}
-- auto-generated, do not reply --
"""


def template_informal_chat_style(row, contact):
    symbol = random.choice(SYMBOL_ALIASES.get(row["symbol"], [row["symbol"]]))
    return f"""hi team, confirming the {row['side'].lower()} of {symbol} qty {row['quantity']} done today,
price came to around {row['price']}, settlement should be {fmt_date(row['settlement_date'])}.
trade ref {row['trade_id']} on our end.
let us know if this doesn't match your books.
thanks,
{contact}
"""


def template_scanned_pdf_style(row, contact):
    symbol = random.choice(SYMBOL_ALIASES.get(row["symbol"], [row["symbol"]]))
    return f"""TRADE  CONFIRMATION   ADVICE

Trade Ref No     {row['trade_id']}
Security          {symbol}
Buy/Sell            {row['side']}
Quantity            {row['quantity']}
Rate                 Rs {row['price']}
Value  Date         {fmt_date(row['settlement_date'])}
Counterparty       {row['counterparty']}

This is a system generated advice   Please verify and revert
in case of any discrepancy within 24 hours of receipt

Authorized  Signatory
{contact}
"""


def template_whatsapp_style(row, contact):
    symbol = random.choice(SYMBOL_ALIASES.get(row["symbol"], [row["symbol"]]))
    first_name = contact.split(". ")[-1] if ". " in contact else contact
    return f"""{first_name}: confirming {row['trade_id']} {symbol} {row['side']} {row['quantity']} @ {row['price']} sd {fmt_date(row['settlement_date'])} ok?
{first_name}: cp {row['counterparty']}, let me know if mismatch"""


def _row_line_for_batch(row):
    symbol = random.choice(SYMBOL_ALIASES.get(row["symbol"], [row["symbol"]]))
    return (f"  {row['trade_id']}  {symbol:<12} {row['side']:<4} "
            f"{row['quantity']:>6} @ {row['price']:<10} SD:{fmt_date(row['settlement_date'])}")


def template_batch_email(rows_batch, contact):
    lines = "\n".join(_row_line_for_batch(r) for r in rows_batch)
    counterparties = {r["counterparty"] for r in rows_batch}
    return f"""From: {contact} <{contact.split('.')[0].lower()}@{list(counterparties)[0].split('-')[0].lower()}.com>
To: ops-recon@ourfirm.com
Subject: EOD Trade Confirmations - {len(rows_batch)} trades - {rows_batch[0]['settlement_date']}

Dear Team,

Please find below confirmation for the following trades executed today:

{lines}

Kindly confirm receipt and advise of any discrepancies at your end.

Regards,
{contact}
"""


SINGLE_TRADE_TEMPLATES = [template_formal_email, template_terse_note,
                           template_informal_chat_style,
                           template_scanned_pdf_style,
                           template_whatsapp_style]


# ---------------------------------------------------------------------
# Format-authentic templates, grounded in ISO 15022 (SWIFT) and
# NSE/SEBI contract note conventions. Synthetic values throughout (fake
# BICs, fake SEBI reg no.) - structurally realistic, never a real record.
# ---------------------------------------------------------------------

BIC_BY_COUNTERPARTY = {
    "ICICI-CUST": "ICICINBBXXX", "HDFC-CUST": "HDFCINBBXXX",
    "KOTAK-CUST": "KKBKINBBXXX", "DEUTSCHE-BROKER": "DEUTDEFFXXX",
    "MORGANSTANLEY-BROKER": "MSNYUS33XXX", "NOMURA-BROKER": "NOMUJPJTXXX",
}

CA_EVENT_CODE = {"MANDATORY": "BONU", "VOLUNTARY": "TEND"}


def _ratio_str(trade_qty, source_value):
    """Recover the approximate CA ratio implied by source_value/quantity
    and render as a clean 'X:Y' - CA_RATIOS in generate_trade_breaks.py
    are deliberately round (1.5/2.0/3.0), so this recovers cleanly."""
    try:
        frac = Fraction(float(source_value) / float(trade_qty)).limit_denominator(3)
        return f"{frac.numerator}:{frac.denominator}"
    except (ZeroDivisionError, ValueError):
        return "2:1"


def template_mt564_ca_notice(trade, brk):
    """SWIFT MT564-style corporate action notification. CAMV (mandatory/
    voluntary indicator) and the NOAC default option code are structural
    parts of ISO 15022, not a Resolvia design choice - grounding the
    always-escalate-voluntary rule in the standard itself, not just an
    internal policy."""
    ca_type = brk["corporate_action_type"]  # MANDATORY | VOLUNTARY
    event_code = CA_EVENT_CODE[ca_type]
    ratio = _ratio_str(trade["quantity"], brk["source_value"])
    ca_ref = f"CA{brk['break_id'][-5:]}{random.randint(10,99)}"
    eff_date = fmt_date(trade["settlement_date"]).replace("-", "")
    isin = trade["isin"]

    lines = [
        ":16R:GENL",
        f":20C::CORP//{ca_ref}",
        ":23G:NEWM",
        ":16S:GENL",
        ":16R:CADETL",
        f":22F::CAEV//{event_code}",
        f":22F::CAMV//{'MAND' if ca_type == 'MANDATORY' else 'VOLU'}",
        f":98A::EFFD//{eff_date}",
        f":35B:ISIN {isin}",
        f":22F::CAON//{ratio}",
        ":16S:CADETL",
    ]
    if ca_type == "VOLUNTARY":
        lines += [
            ":16R:CAOPTN",
            ":13A::CAON//001",
            ":22F::CAOP//SECU",
            ":16S:CAOPTN",
            ":16R:CAOPTN",
            ":13A::CAON//002",
            ":22F::CAOP//CASH",
            ":16S:CAOPTN",
            ":16R:CAOPTN",
            ":13A::CAON//003",
            ":22F::CAOP//NOAC",
            ":16S:CAOPTN",
            ":16R:ADDINFO",
            f":70E::ADTX//ELECTION REQUIRED BY {eff_date}. ABSENT INSTRUCTION,",
            ":70E::ADTX//DEFAULT OPTION NOAC (NO ACTION) WILL APPLY.",
            ":16S:ADDINFO",
        ]
    else:
        lines += [
            ":16R:ADDINFO",
            f":70E::ADTX//RATIO {ratio} - NO ELECTION REQUIRED, MECHANICAL EVENT.",
            ":16S:ADDINFO",
        ]

    header = (f"MT564 CORPORATE ACTION NOTIFICATION (synthetic/demo)\n"
              f"Sender: {BIC_BY_COUNTERPARTY.get(trade['counterparty'], 'DEMOXXBBXXX')}  "
              f"Receiver: OURFIRMINBBXXX\n"
              f"Ref: {trade['trade_id']}  ISIN: {isin}\n")
    return header + "\n".join(lines) + "\n"


def template_mt54x_settlement(trade, settlement, brk):
    """SWIFT MT54x-style (MT540-548) settlement instruction/status
    message. Field tags follow the ISO 15022 :16R:/:16S: block structure
    (GENL/TRADDET/FIAC/SETDET) and :95Q: party-code convention."""
    ref = f"SEME{trade['trade_id'][-6:]}{random.randint(10,99)}"
    is_missing_instruction = settlement.get("instruction_status") == "MISSING"
    msg_type = "MT548" if is_missing_instruction else "MT542"
    if is_missing_instruction:
        status_narr = "NO SETTLEMENT INSTRUCTION ON FILE - REJECTED, NOT MATCHED"
    else:
        status_narr = {
            "FAILED": "SETTLEMENT INSTRUCTION REJECTED - SSI MISMATCH",
            "PENDING": "AWAITING COUNTERPARTY CONFIRMATION",
            "SETTLED": "SETTLEMENT CONFIRMED",
        }.get(settlement.get("settlement_status", ""), "STATUS UNKNOWN")

    lines = [
        ":16R:GENL",
        f":20C::SEME//{ref}",
        ":23G:NEWM",
        ":16S:GENL",
        ":16R:TRADDET",
        f":98A::SETT//{settlement.get('settlement_date', '').replace('-', '')}",
        f":98A::TRAD//{trade['trade_date'].replace('-', '')}",
        f":35B:ISIN {trade['isin']}",
        ":16S:TRADDET",
        ":16R:FIAC",
        f":36B::SETT//UNIT/{settlement.get('quantity', trade['quantity'])}",
        ":16S:FIAC",
        ":16R:SETDET",
        ":22F::SETR//TRAD",
        f":95Q::REAG//{trade['counterparty']}",
        f":95Q::DECU//{settlement.get('ssi_code') or 'NONE ON FILE'}",
        f":25D::PROC//{settlement.get('settlement_status', 'UNKNOWN')}",
        ":16S:SETDET",
    ]
    header = (f"{msg_type} SETTLEMENT MESSAGE (synthetic/demo)\n"
              f"Sender: CUSTODIANINBBXXX  Receiver: OURFIRMINBBXXX\n"
              f"Status: {status_narr}\n")
    return header + "\n".join(lines) + "\n"


SEBI_REG_BY_COUNTERPARTY = {
    "ICICI-CUST": "INZ000183631", "HDFC-CUST": "INZ000186937",
    "KOTAK-CUST": "INZ000200137", "DEUTSCHE-BROKER": "INZ000174330",
    "MORGANSTANLEY-BROKER": "INZ000209137", "NOMURA-BROKER": "INZ000220236",
}


def template_contract_note(trade, brk):
    """NSE/SEBI-style contract note. Field list (SEBI reg no., UCC,
    STT/exchange charges/SEBI turnover fee/stamp duty/GST breakdown)
    follows the exchange-prescribed contract note format; brokerage/
    charge rates below are illustrative, not the current SEBI schedule."""
    qty = int(float(trade["confirmed_quantity"] or trade["quantity"]))
    price = float(trade["confirmed_price"] or trade["price"])
    side = trade["side"]
    value = round(qty * price, 2)
    brokerage = round(value * 0.0003, 2)
    stt = round(value * 0.001, 2) if side == "SELL" else 0.0
    exch_charges = round(value * 0.0000297, 2)
    sebi_fee = round(value * 0.000001, 2)
    stamp_duty = round(value * 0.00015, 2) if side == "BUY" else 0.0
    gst = round((brokerage + exch_charges) * 0.18, 2)
    net = round(value + brokerage + stt + exch_charges + sebi_fee + stamp_duty + gst
                if side == "BUY" else
                value - brokerage - stt - exch_charges - sebi_fee - gst, 2)
    ucc = f"UCC{trade['trade_id'][-6:]}"
    cn_no = f"CN{trade['trade_date'].replace('-', '')}{trade['trade_id'][-4:]}"

    return f"""CONTRACT NOTE (CUM/DEMO) - NSE CAPITAL MARKET SEGMENT

Member: {trade['counterparty']}  SEBI Reg No: {SEBI_REG_BY_COUNTERPARTY.get(trade['counterparty'], 'INZ000000000')}
Compliance Officer: R. Menon | compliance@{trade['counterparty'].split('-')[0].lower()}.com
Investor Complaints: complaints@{trade['counterparty'].split('-')[0].lower()}.com

Contract Note No : {cn_no}
Trade Date       : {fmt_date(trade['confirmed_trade_date'] or trade['trade_date'])}
Settlement No     : SETT-{trade['settlement_date'].replace('-', '')}
Unique Client Code: {ucc}
Trading Code      : {trade['trade_id']}

Security    : {trade['security']}  ISIN: {trade['isin']}
Buy/Sell    : {side}
Quantity    : {qty}
Rate        : INR {price}
Trade Value : INR {value}

Brokerage                    : INR {brokerage}
Securities Transaction Tax   : INR {stt}
Exchange Transaction Charges : INR {exch_charges}
SEBI Turnover Fees           : INR {sebi_fee}
Stamp Duty                   : INR {stamp_duty}
GST (18%)                    : INR {gst}
-------------------------------------------
Net Amount {'Payable' if side == 'BUY' else 'Receivable'} : INR {net}

This contract note is issued subject to the rules, byelaws of NSE.
"""





def build_confirm_row(trade, brk):
    """The document reflects the external/confirmed view for TRADE-family
    breaks (that's the whole point - the confirmation disagrees with the
    booking); for every other family it reflects the clean booked trade,
    since the trade itself isn't what's wrong."""
    if brk["break_type"] == "TRADE":
        return {
            "trade_id": trade["trade_id"],
            "symbol": trade["security"],
            "quantity": trade["confirmed_quantity"] or trade["quantity"],
            "price": trade["confirmed_price"] or trade["price"],
            "counterparty": trade["confirmed_counterparty"] or trade["counterparty"],
            "side": trade["side"],
            "trade_date": trade["confirmed_trade_date"] or trade["trade_date"],
            "settlement_date": trade["settlement_date"],
        }
    return {
        "trade_id": trade["trade_id"], "symbol": trade["security"],
        "quantity": trade["quantity"], "price": trade["price"],
        "counterparty": trade["counterparty"], "side": trade["side"],
        "trade_date": trade["trade_date"], "settlement_date": trade["settlement_date"],
    }


def _mapping_row(doc_id, brk, trade, template_name):
    return {
        "doc_id": doc_id, "break_id": brk["break_id"], "trade_id": trade["trade_id"],
        "symbol": trade["security"], "quantity": trade["quantity"], "price": trade["price"],
        "counterparty": trade["counterparty"], "settlement_date": trade["settlement_date"],
        "break_type": brk["break_type"], "mismatch_type": brk["mismatch_type"],
        "root_cause": brk["root_cause"], "severity": brk["severity"],
        "corporate_action_type": brk["corporate_action_type"],
        "template_used": template_name,
    }


def main(trades_csv="trades.csv", breaks_csv="breaks.csv", settlements_csv="settlements.csv",
         out_dir="broker_confirms"):
    with open(trades_csv, newline="") as f:
        trades_by_id = {r["trade_id"]: r for r in csv.DictReader(f)}
    with open(settlements_csv, newline="") as f:
        settlements_by_trade = {r["trade_id"]: r for r in csv.DictReader(f)}
    with open(breaks_csv, newline="") as f:
        all_breaks = [r for r in csv.DictReader(f) if r["needs_evidence_bundle"] == "True"]

    os.makedirs(out_dir, exist_ok=True)
    mapping = []
    doc_counter = 1

    # Route by family/CA-type: CA/SETTLEMENT/TRADE breaks get the format-
    # authentic single-document templates (never batched - a settlement
    # message or contract note is always one instruction, not a digest
    # email). POSITION(non-CA)/CASH breaks keep the original plain-English
    # ops-correspondence templates, including the batch-email pool.
    ca_breaks = [b for b in all_breaks if b["corporate_action_type"]]
    settlement_breaks = [b for b in all_breaks if b["break_type"] == "SETTLEMENT" and not b["corporate_action_type"]]
    trade_breaks = [b for b in all_breaks if b["break_type"] == "TRADE" and not b["corporate_action_type"]]
    breaks = [b for b in all_breaks
              if b["break_type"] in ("POSITION", "CASH") and not b["corporate_action_type"]]

    for brk in ca_breaks:
        trade = trades_by_id[brk["source_record_id"]]
        doc_id = f"doc_{doc_counter:04d}"; doc_counter += 1
        text = template_mt564_ca_notice(trade, brk)
        with open(os.path.join(out_dir, f"{doc_id}.txt"), "w") as f:
            f.write(text)
        mapping.append(_mapping_row(doc_id, brk, trade, "template_mt564_ca_notice"))

    for brk in settlement_breaks:
        trade = trades_by_id[brk["source_record_id"]]
        settlement = settlements_by_trade[trade["trade_id"]]
        doc_id = f"doc_{doc_counter:04d}"; doc_counter += 1
        text = template_mt54x_settlement(trade, settlement, brk)
        with open(os.path.join(out_dir, f"{doc_id}.txt"), "w") as f:
            f.write(text)
        mapping.append(_mapping_row(doc_id, brk, trade, "template_mt54x_settlement"))

    for brk in trade_breaks:
        trade = trades_by_id[brk["source_record_id"]]
        doc_id = f"doc_{doc_counter:04d}"; doc_counter += 1
        text = template_contract_note(trade, brk)
        with open(os.path.join(out_dir, f"{doc_id}.txt"), "w") as f:
            f.write(text)
        mapping.append(_mapping_row(doc_id, brk, trade, "template_contract_note"))

    random.shuffle(breaks)
    n_batch_pool = max(0, len(breaks) - 200)  # rest go into batch emails
    single_breaks, batch_breaks = breaks[:len(breaks) - n_batch_pool], breaks[len(breaks) - n_batch_pool:]

    for brk in single_breaks:
        trade = trades_by_id[brk["source_record_id"]]
        row = build_confirm_row(trade, brk)
        doc_id = f"doc_{doc_counter:04d}"
        doc_counter += 1
        template = random.choice(SINGLE_TRADE_TEMPLATES)
        contact = random.choice(CONTACT_NAMES)
        text = template(row, contact)

        with open(os.path.join(out_dir, f"{doc_id}.txt"), "w") as f:
            f.write(text)

        mapping.append(_mapping_row(doc_id, brk, trade, template.__name__))

    idx = 0
    batch_size_range = (5, 10)
    while idx < len(batch_breaks):
        size = random.randint(*batch_size_range)
        batch = batch_breaks[idx:idx + size]
        idx += size
        if len(batch) < 2:
            break

        rows_batch = [build_confirm_row(trades_by_id[b["source_record_id"]], b) for b in batch]
        doc_id = f"doc_{doc_counter:04d}"
        doc_counter += 1
        contact = random.choice(CONTACT_NAMES)
        text = template_batch_email(rows_batch, contact)

        with open(os.path.join(out_dir, f"{doc_id}.txt"), "w") as f:
            f.write(text)

        for brk, trade in zip(batch, [trades_by_id[b["source_record_id"]] for b in batch]):
            mapping.append({
                "doc_id": doc_id, "break_id": brk["break_id"], "trade_id": trade["trade_id"],
                "symbol": trade["security"], "quantity": trade["quantity"], "price": trade["price"],
                "counterparty": trade["counterparty"], "settlement_date": trade["settlement_date"],
                "break_type": brk["break_type"], "mismatch_type": brk["mismatch_type"],
                "root_cause": brk["root_cause"], "severity": brk["severity"],
                "corporate_action_type": brk["corporate_action_type"],
                "template_used": "template_batch_email",
            })

    with open(f"{out_dir}_mapping.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(mapping[0].keys()))
        writer.writeheader()
        writer.writerows(mapping)

    n_docs = doc_counter - 1
    print(f"Generated {n_docs} documents in ./{out_dir}/ covering {len(mapping)} evidence-bundle breaks")
    print(f"Ground-truth mapping: {out_dir}_mapping.csv")


if __name__ == "__main__":
    main()
