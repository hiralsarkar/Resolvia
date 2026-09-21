"""
theme.py - "Command Center" design system (v3, 2026-09-17).

Unifies the operational app with the hero animation's visual language
(same dark void/graphite surfaces, same cyan/violet/magenta/amber/
emerald semantic palette, same Bricolage Grotesque + Manrope +
JetBrains Mono type system, same glow/pulse motion grammar) so the
marketing hero and the actual tool read as one product, not two skins.
Color still carries meaning first: cyan=data/detection, violet=AI
reasoning, magenta=recommendation, amber=human-authorization attention,
emerald=verified/resolved - the same mapping the hero uses per agent.
"""

COLORS = {
    "bone": "#0A0B10",           # base canvas (was warm-light, now void)
    "surface": "#12141D",        # raised card
    "surface_sunken": "#171A25", # recessed panel
    "ink": "#F2F3F8",            # primary text (near-white on dark)
    "ink_soft": "#8B90A3",       # secondary text
    "ink_faint": "#565B6E",      # tertiary text
    "hairline": "#232733",

    "accent": "#4CE0FF",         # cyan - brand/interactive default
    "accent_soft": "rgba(76,224,255,0.14)",
    "accent_deep": "#1FA8C9",

    "violet": "#A78BFA",         # AI reasoning (Investigation, RCA)
    "violet_soft": "rgba(167,139,250,0.14)",
    "magenta": "#FF7AC6",        # recommendation (Resolution Proposal)
    "magenta_soft": "rgba(255,122,198,0.14)",

    "forest": "#34E5A6",         # verified / resolved / low severity
    "forest_soft": "rgba(52,229,166,0.14)",
    "amber": "#FFB454",          # human-authorization attention
    "amber_soft": "rgba(255,180,84,0.14)",
    "signal": "#FF5C7A",         # critical / rejected / reopened
    "signal_soft": "rgba(255,92,122,0.14)",
    "slate": "#7A8296",
    "slate_soft": "rgba(122,130,150,0.14)",
}

FAMILY_COLOR = {
    "POSITION": COLORS["accent"],
    "CASH": COLORS["forest"],
    "SETTLEMENT": COLORS["amber"],
    "TRADE": COLORS["slate"],
}

SEVERITY_COLOR = {
    "P0": (COLORS["signal"], COLORS["signal_soft"]),
    "P1": (COLORS["amber"], COLORS["amber_soft"]),
    "P2": (COLORS["forest"], COLORS["forest_soft"]),
}

STATUS_COLOR = {
    "CLOSED": (COLORS["forest"], COLORS["forest_soft"]),
    "REOPENED": (COLORS["signal"], COLORS["signal_soft"]),
    "AWAITING_APPROVAL": (COLORS["amber"], COLORS["amber_soft"]),
    "REJECTED": (COLORS["signal"], COLORS["signal_soft"]),
    "OPEN": (COLORS["slate"], COLORS["slate_soft"]),
    "NOT_STARTED": (COLORS["ink_faint"], COLORS["surface_sunken"]),
    "HALTED_DATA_QUALITY": (COLORS["signal"], COLORS["signal_soft"]),
    "IN_REVIEW": (COLORS["violet"], COLORS["violet_soft"]),
    "ESCALATED": (COLORS["magenta"], COLORS["magenta_soft"]),
}

# Human-readable labels for the 20 internal root_cause enum keys - shown
# instead of raw SETL_MISSING_INSTRUCTION-style identifiers anywhere a
# person (not a downstream script) reads them.
ROOT_CAUSE_LABEL = {
    "POS_MISSING_BOOKING": "Missing Booking",
    "POS_WRONG_QUANTITY": "Wrong Quantity",
    "POS_TIMING_DIFFERENCE": "Timing Difference",
    "CA_INCORRECT_ENTITLEMENT": "CA - Incorrect Entitlement",
    "CA_MANDATORY_NOT_REFLECTED": "CA - Mandatory Not Reflected",
    "CA_VOLUNTARY_DECISION": "CA - Voluntary Decision Pending",
    "CASH_MISSING_ENTRY": "Missing Cash Entry",
    "CASH_DUPLICATE_ENTRY": "Duplicate Cash Entry",
    "CASH_WRONG_AMOUNT": "Wrong Cash Amount",
    "CASH_FX_INPUT_DIFFERENCE": "FX Input Difference",
    "SETL_WRONG_SSI": "Wrong Settlement Instruction (SSI)",
    "SETL_LATE_COUNTERPARTY": "Late Counterparty Settlement",
    "SETL_MISSING_INSTRUCTION": "Missing Settlement Instruction",
    "SETL_INCORRECT_DATE": "Incorrect Settlement Date",
    "TRADE_PRICE_MISMATCH": "Price Mismatch",
    "TRADE_QUANTITY_MISMATCH": "Quantity Mismatch",
    "TRADE_DATE_MISMATCH": "Trade Date Mismatch",
    "TRADE_COUNTERPARTY_ID_MISMATCH": "Counterparty ID Mismatch",
    "CONF_MISSING": "Confirmation Missing",
    "CONF_DISAGREEMENT": "Confirmation Disagreement",
}


STATUS_LABEL = {
    "CLOSED": "Resolved", "REOPENED": "Needs another look", "AWAITING_APPROVAL": "Waiting for approval",
    "REJECTED": "Rejected", "OPEN": "Open", "NOT_STARTED": "Not started yet",
    "HALTED_DATA_QUALITY": "Stopped - data problem", "IN_REVIEW": "In review", "ESCALATED": "Escalated to senior", "CASE_CREATED": "Started",
}
SEVERITY_LABEL = {"P0": "Critical", "P1": "High", "P2": "Low"}
TIER_LABEL = {"CONTROLLED_ACTION": "Needs approval", "PROPOSAL": "No approval needed"}

_EVIDENCE = {
    "structured:trade": "Trade record", "structured:position": "Position record",
    "structured:cash_transactions": "Cash records", "structured:settlement": "Settlement record",
}


def humanize(text):
    """Turn internal codes in backend-written sentences into plain words."""
    import re
    if not isinstance(text, str):
        return text
    for k in sorted(ROOT_CAUSE_LABEL, key=len, reverse=True):
        text = text.replace(k, ROOT_CAUSE_LABEL[k])
    for k, v in TIER_LABEL.items():
        text = text.replace(k, v)
    text = re.sub(r"\bconfidence\b", "certainty", text)
    text = re.sub(r"\bP([012])\b", lambda m: SEVERITY_LABEL["P" + m.group(1)], text)
    return text


def humanize_evidence(code):
    if code in _EVIDENCE:
        return _EVIDENCE[code]
    if code.startswith("document:"):
        return "Document " + code.split(":", 1)[1].split(" ")[0]
    if code.startswith("related_document:"):
        return "Similar case " + code.split(":", 1)[1]
    if code.startswith("ca_reference:"):
        return "Rule: " + code.split(":", 1)[1]
    return code


def root_cause_label(key):
    return ROOT_CAUSE_LABEL.get(key, key.replace("_", " ").title())


def inject_global_css():
    import streamlit as st
    c = COLORS
    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Bricolage+Grotesque:opsz,wght@12..96,500;12..96,600;12..96,700;12..96,800&family=Manrope:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600;700&display=swap');

:root {{
  --bone: {c['bone']}; --surface: {c['surface']}; --surface-sunken: {c['surface_sunken']};
  --ink: {c['ink']}; --ink-soft: {c['ink_soft']}; --ink-faint: {c['ink_faint']};
  --hairline: {c['hairline']}; --hairline-bright: rgba(255,255,255,0.18);
  --accent: {c['accent']}; --accent-soft: {c['accent_soft']}; --accent-deep: {c['accent_deep']};
  --violet: {c['violet']}; --violet-soft: {c['violet_soft']};
  --magenta: {c['magenta']}; --magenta-soft: {c['magenta_soft']};
  --forest: {c['forest']}; --forest-soft: {c['forest_soft']};
  --amber: {c['amber']}; --amber-soft: {c['amber_soft']};
  --signal: {c['signal']}; --signal-soft: {c['signal_soft']};
  --slate: {c['slate']}; --slate-soft: {c['slate_soft']};
}}

* {{ transition: background-color 0.18s ease, border-color 0.18s ease, box-shadow 0.18s ease, color 0.18s ease; }}

html, body, .stApp {{
  background:
    radial-gradient(ellipse 60% 40% at 12% 0%, rgba(76,224,255,0.05), transparent 60%),
    radial-gradient(ellipse 55% 45% at 100% 100%, rgba(52,229,166,0.04), transparent 60%),
    var(--bone) !important;
  color: var(--ink);
  font-family: 'Manrope', -apple-system, sans-serif;
}}
::selection {{ background: var(--accent-soft); color: var(--ink); }}

#MainMenu, footer, header[data-testid="stHeader"] {{ visibility: hidden; height: 0; }}
.block-container {{ padding-top: 1.5rem; padding-bottom: 3rem; max-width: 1240px; }}

h1, h2, h3, .headline {{
  font-family: 'Bricolage Grotesque', 'Manrope', sans-serif !important;
  color: var(--ink) !important; font-weight: 800 !important; letter-spacing: -0.03em;
}}
p, span, div, label {{ color: var(--ink); }}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {{
  background: linear-gradient(180deg, #0d0f16, #08090d) !important;
  border-right: 1px solid var(--hairline);
}}
section[data-testid="stSidebar"] * {{ color: #C9CCDA !important; }}
section[data-testid="stSidebar"] .stRadio label {{ font-family: 'Manrope', sans-serif; font-weight: 500; font-size: 0.92rem; }}
section[data-testid="stSidebar"] hr {{ border-color: var(--hairline); }}

/* ---------- brand mark (a real button styled to look like the wordmark,
   so clicking "Resolvia" in the sidebar opens the Command Center) -
   Streamlit exposes a widget's key as a literal CSS class st-key-<key>,
   which is a more reliable hook than DOM-order sibling selectors. ---------- */
div.st-key-home_brand_btn button {{
  font-family: 'Bricolage Grotesque', sans-serif !important; font-weight: 800 !important;
  font-size: 1.6rem !important; letter-spacing: -0.03em !important; line-height: 1 !important;
  color: #F5F6FA !important; background: transparent !important; border: none !important;
  padding: 0 !important; box-shadow: none !important; text-align: left !important;
  justify-content: flex-start !important; width: auto !important; min-height: 0 !important;
}}
div.st-key-home_brand_btn button:hover {{
  color: var(--accent) !important; background: transparent !important; box-shadow: none !important;
}}
div.st-key-home_brand_btn button p {{ font-size: 1.6rem !important; font-weight: 800 !important; line-height: 1 !important; }}
div.st-key-home_brand_btn button:focus:not(:active) {{ box-shadow: none !important; outline: none !important; }}
.resolvia-mark {{
  font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 1.6rem;
  letter-spacing: -0.03em; color: #F5F6FA !important; line-height: 1;
}}
.resolvia-mark .dot {{ color: var(--accent) !important; text-shadow: 0 0 12px var(--accent); }}
.resolvia-tagline {{
  font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; font-weight: 500;
  letter-spacing: 0.13em; text-transform: uppercase; color: #565E76 !important; margin-top: 5px;
}}

/* ---------- eyebrow / section labels ---------- */
.eyebrow {{
  font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 600;
  letter-spacing: 0.13em; text-transform: uppercase; color: var(--accent) !important;
  margin-bottom: 2px; display: block;
}}

/* ---------- numbers ---------- */
.mono, .num {{ font-family: 'JetBrains Mono', monospace; font-variant-numeric: tabular-nums; }}

/* ---------- cards ---------- */
.rv-card {{
  background: linear-gradient(160deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
  border: 1px solid var(--hairline); border-radius: 14px; padding: 22px 24px;
  backdrop-filter: blur(10px);
}}
.rv-card:hover {{ border-color: var(--hairline-bright); }}

/* ---------- KPI tile ---------- */
.kpi-tile {{
  background: linear-gradient(160deg, rgba(255,255,255,0.035), rgba(255,255,255,0.01));
  border: 1px solid var(--hairline); border-radius: 14px;
  padding: 16px 18px; height: 100%; min-width: 0; position: relative; overflow: hidden;
}}
.kpi-tile::before {{
  content: ""; position: absolute; top: 0; left: 0; right: 0; height: 2px;
  background: var(--accent); box-shadow: 0 0 8px var(--accent);
  transform: scaleX(0); transform-origin: left;
  animation: kpi-bar 0.6s cubic-bezier(.2,.7,.3,1) forwards; animation-delay: 0.1s;
}}
@keyframes kpi-bar {{ to {{ transform: scaleX(1); }} }}
.kpi-tile:hover {{ border-color: var(--hairline-bright); }}
.kpi-value {{
  font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 1.5rem; color: var(--ink) !important;
  line-height: 1.15; margin: 5px 0 2px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}}
.kpi-label {{
  font-family: 'JetBrains Mono', monospace; font-size: 0.62rem; font-weight: 600;
  letter-spacing: 0.07em; text-transform: uppercase; color: var(--ink-soft) !important;
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis; display: block;
}}
.kpi-sub {{ font-family: 'Manrope', sans-serif; font-size: 0.74rem; color: var(--ink-faint) !important; }}

/* radio buttons pick up brand accent */
[data-testid="stSidebar"] .stRadio [role="radiogroup"] label div:first-child > div {{ border-color: var(--accent) !important; }}
.stRadio [aria-checked="true"] div:first-child > div {{ background-color: var(--accent) !important; }}

/* ---------- pills / badges ---------- */
.pill {{
  display: inline-flex; align-items: center; gap: 5px; padding: 3px 11px 4px 11px;
  border-radius: 999px; font-family: 'JetBrains Mono', monospace; font-size: 0.7rem; font-weight: 600;
  letter-spacing: 0.02em; white-space: nowrap; border: 1px solid transparent;
}}
.pill-dot {{ width: 6px; height: 6px; border-radius: 50%; display: inline-block; box-shadow: 0 0 6px currentColor; }}
.pill-live .pill-dot {{ animation: pulse-dot 1.6s ease-in-out infinite; }}

/* ---------- buttons ---------- */
.stButton > button {{
  font-family: 'Manrope', sans-serif !important; font-weight: 700 !important;
  border-radius: 10px !important; border: 1.5px solid var(--accent) !important;
  color: var(--accent) !important; background: transparent !important; padding: 0.5rem 1.1rem !important;
}}
.stButton > button:hover {{ background: var(--accent-soft) !important; box-shadow: 0 0 20px -2px var(--accent); }}
.stButton > button[kind="primary"] {{
  background: var(--accent) !important; color: #04141A !important; border-color: var(--accent) !important;
  box-shadow: 0 0 20px -4px var(--accent);
}}
.stButton > button[kind="primary"]:hover {{ background: var(--accent-deep) !important; box-shadow: 0 0 28px -2px var(--accent); }}

/* ---------- guided next-step: big, centered, gently pulsing ---------- */
.st-key-cc_open_ops, .st-key-ops_start_analysis, .st-key-ci_start_analysis, .st-key-ci_go_ops, .st-key-ci_go_resolution, .st-key-rc_go_ops, .st-key-rc_go_ci, .st-key-rc_approve, .st-key-rc_next_case {{ width: 100% !important; }}
.st-key-cc_open_ops .stButton, .st-key-ops_start_analysis .stButton, .st-key-ci_start_analysis .stButton, .st-key-ci_go_ops .stButton, .st-key-ci_go_resolution .stButton, .st-key-rc_go_ops .stButton, .st-key-rc_go_ci .stButton, .st-key-rc_approve .stButton, .st-key-rc_next_case .stButton {{ width: 100% !important; }}
.st-key-cc_open_ops button, .st-key-ops_start_analysis button, .st-key-ci_start_analysis button, .st-key-ci_go_ops button, .st-key-ci_go_resolution button, .st-key-rc_go_ops button, .st-key-rc_go_ci button, .st-key-rc_approve button, .st-key-rc_next_case button {{
  width: 100%; padding: 0.95rem 1.4rem !important; font-size: 1.12rem !important;
  border-radius: 14px !important; animation: cta-pulse 2.2s ease-in-out infinite;
}}
@keyframes cta-pulse {{
  0%, 100% {{ box-shadow: 0 0 18px -4px var(--accent), 0 0 0 0 rgba(76,224,255,0.45); }}
  50% {{ box-shadow: 0 0 34px -2px var(--accent), 0 0 0 10px rgba(76,224,255,0); }}
}}
.st-key-cc_open_ops button {{ padding: 1.1rem 1.4rem !important; font-size: 1.25rem !important; }}

.cta-panel {{
  text-align: center; margin: 4px auto 14px auto; padding: 16px 22px; max-width: 720px;
  border: 1px solid rgba(76,224,255,0.35); border-radius: 14px; background: var(--accent-soft);
}}
.cta-panel.quiet {{ border-color: var(--hairline); background: rgba(255,255,255,0.02); }}
.cta-panel-text {{ font-family: 'Manrope', sans-serif; font-size: 1.05rem; font-weight: 500; color: var(--ink); }}
.cta-panel-text b {{ color: var(--accent); }}

.step-banner {{
  display: flex; align-items: center; gap: 16px; margin: 6px 0 18px 0; padding: 14px 18px;
  border: 1px solid var(--hairline); border-radius: 14px; background: rgba(255,255,255,0.025);
}}
.step-pips {{ display: flex; gap: 6px; }}
.step-pip {{ width: 26px; height: 6px; border-radius: 999px; background: var(--hairline-bright); }}
.step-pip.on {{ background: var(--accent); box-shadow: 0 0 8px var(--accent); }}
.step-banner-title {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 700; font-size: 1.15rem; color: var(--ink); }}
.step-banner-hint {{ font-family: 'Manrope', sans-serif; font-size: 0.95rem; color: var(--ink-soft); margin-top: 2px; }}

.st-key-rc_reject, .st-key-rc_reject .stButton {{ width: 100% !important; }}
.st-key-rc_reject button {{ width: 100%; padding: 0.95rem 1.4rem !important; font-size: 1.12rem !important; border-radius: 14px !important; }}
div[data-reject="1"] .stButton > button {{ border-color: var(--ink-faint) !important; color: var(--ink-soft) !important; }}
div[data-reject="1"] .stButton > button:hover {{ background: var(--signal-soft) !important; border-color: var(--signal) !important; color: var(--signal) !important; box-shadow: 0 0 20px -4px var(--signal); }}

/* ---------- tabs as editorial nav ---------- */
.stTabs [data-baseweb="tab-list"] {{ gap: 28px; border-bottom: 1.5px solid var(--hairline); }}
.stTabs [data-baseweb="tab"] {{ font-family: 'Manrope', sans-serif; font-weight: 600; font-size: 0.88rem; color: var(--ink-faint) !important; padding: 4px 2px 12px 2px; background: transparent; }}
.stTabs [aria-selected="true"] p {{ color: var(--ink) !important; }}
.stTabs [data-baseweb="tab-highlight"] {{ background-color: var(--accent) !important; height: 2.5px !important; box-shadow: 0 0 8px var(--accent); }}

/* ---------- dataframe ---------- */
[data-testid="stDataFrame"] {{ border: 1px solid var(--hairline); border-radius: 12px; overflow: hidden; }}

/* ---------- stepper: the real Orchestrator state machine ---------- */
.stepper {{ display: flex; align-items: flex-start; width: 100%; margin: 8px 0 4px 0; }}
.step {{ flex: 1; text-align: center; position: relative; opacity: 0; animation: step-in 0.45s cubic-bezier(.2,.7,.3,1) forwards; }}
@keyframes step-in {{ from {{ opacity: 0; transform: translateY(6px); }} to {{ opacity: 1; transform: translateY(0); }} }}
.step-line {{ position: absolute; top: 13px; left: -50%; width: 100%; height: 2px; background: var(--hairline); z-index: 0; transition: background 0.5s ease, box-shadow 0.5s ease; }}
.step:first-child .step-line {{ display: none; }}
.step-line.done {{ background: var(--forest); box-shadow: 0 0 6px var(--forest); }}
.step-dot {{
  width: 26px; height: 26px; border-radius: 50%; margin: 0 auto 8px auto; position: relative; z-index: 1;
  display: flex; align-items: center; justify-content: center;
  font-family: 'JetBrains Mono', monospace; font-weight: 700; font-size: 0.72rem;
  border: 2px solid var(--hairline); background: var(--surface); color: var(--ink-faint);
}}
.step-dot.done {{ background: var(--forest); border-color: var(--forest); color: #04150F; box-shadow: 0 0 12px -2px var(--forest); }}
.step-dot.active {{ background: var(--accent); border-color: var(--accent); color: #04141A; animation: pulse-glow 1.4s ease-in-out infinite; }}
.step-dot.blocked {{ background: var(--signal); border-color: var(--signal); color: #1A0408; box-shadow: 0 0 12px -2px var(--signal); }}
@keyframes pulse-glow {{ 0%,100% {{ box-shadow: 0 0 0 0 rgba(76,224,255,0.45); }} 50% {{ box-shadow: 0 0 0 8px rgba(76,224,255,0); }} }}
@keyframes pulse-dot {{ 0%,100% {{ opacity: 1; transform: scale(1); }} 50% {{ opacity: 0.35; transform: scale(0.75); }} }}
.step-label {{ font-family: 'JetBrains Mono', monospace; font-size: 0.64rem; font-weight: 500; color: var(--ink-soft) !important; letter-spacing: 0.02em; line-height: 1.2; }}

.orchestrator-note {{
  display: flex; align-items: center; gap: 8px; margin: 10px 0 2px;
  font-family: 'JetBrains Mono', monospace; font-size: 0.68rem; color: var(--ink-faint);
  padding: 6px 12px; border: 1px dashed var(--hairline); border-radius: 999px; width: fit-content;
}}
.orchestrator-note .od {{ width: 6px; height: 6px; border-radius: 50%; background: #EEF0FF; box-shadow: 0 0 8px #EEF0FF; animation: pulse-dot 1.8s ease-in-out infinite; }}

/* ---------- live agent feed (st.status-driven) ---------- */
.agent-feed-row {{ display: flex; align-items: center; gap: 10px; padding: 6px 0; font-family: 'Manrope', sans-serif; font-size: 0.85rem; color: var(--ink-soft); animation: feed-in 0.35s ease both; }}
@keyframes feed-in {{ from {{ opacity: 0; transform: translateX(-6px); }} to {{ opacity: 1; transform: translateX(0); }} }}
.agent-feed-dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--accent); box-shadow: 0 0 6px var(--accent); flex-shrink: 0; }}
.agent-feed-name {{ font-weight: 700; color: var(--ink); }}

/* ---------- evidence / timeline ---------- */
.doc-box {{
  background: var(--surface-sunken); border: 1px dashed var(--hairline); border-radius: 10px;
  padding: 14px 16px; font-family: 'JetBrains Mono', monospace; font-size: 0.78rem;
  color: var(--ink-soft); white-space: pre-wrap; max-height: 220px; overflow-y: auto;
}}
.timeline-row {{ display: flex; gap: 14px; padding: 7px 0; border-bottom: 1px solid var(--hairline); font-size: 0.82rem; }}
.timeline-row:last-child {{ border-bottom: none; }}
.timeline-time {{ font-family: 'JetBrains Mono', monospace; color: var(--ink-faint); font-size: 0.72rem; min-width: 74px; }}
.timeline-event {{ font-weight: 700; color: var(--ink); min-width: 190px; }}
.timeline-detail {{ color: var(--ink-soft); }}

hr {{ border-color: var(--hairline) !important; margin: 1.2rem 0 !important; }}

/* ---------- alerts ---------- */
[data-testid="stAlert"] {{ border-radius: 10px !important; font-family: 'Manrope', sans-serif !important; border: 1px solid transparent !important; }}
div[data-testid="stNotificationContentInfo"] {{ color: var(--ink) !important; }}
[data-testid="stAlertContainer"]:has(div[data-testid="stNotificationContentInfo"]) {{ background: var(--surface-sunken) !important; border-color: var(--hairline) !important; }}
[data-testid="stAlertContainer"]:has(div[data-testid="stNotificationContentWarning"]) {{ background: var(--amber-soft) !important; border-color: var(--amber) !important; }}
div[data-testid="stNotificationContentWarning"] {{ color: {c['amber']} !important; }}
[data-testid="stAlertContainer"]:has(div[data-testid="stNotificationContentError"]) {{ background: var(--signal-soft) !important; border-color: var(--signal) !important; }}
div[data-testid="stNotificationContentError"] {{ color: {c['signal']} !important; }}

/* ---------- metric widgets ---------- */
[data-testid="stMetricValue"] {{ font-family: 'JetBrains Mono', monospace !important; color: var(--ink) !important; }}
[data-testid="stMetricLabel"] {{ font-family: 'Manrope', sans-serif !important; color: var(--ink-soft) !important; }}

/* ---------- text inputs / textareas / selects ---------- */
.stTextInput input, .stTextArea textarea {{ background: var(--surface) !important; border: 1px solid var(--hairline) !important; border-radius: 8px !important; color: var(--ink) !important; }}
[data-baseweb="select"] > div {{ background: var(--surface) !important; border-color: var(--hairline) !important; color: var(--ink) !important; }}
[data-baseweb="popover"] {{ background: var(--surface) !important; }}
[data-testid="stMultiSelect"] span[data-baseweb="tag"] {{ background: var(--accent-soft) !important; color: var(--accent) !important; }}

/* ---------- st.status (agentic run feed) ---------- */
[data-testid="stExpander"] {{ border-radius: 12px !important; border-color: var(--hairline) !important; background: var(--surface-sunken) !important; }}

/* ---------- eye-catching sidebar ---------- */
section[data-testid="stSidebar"][aria-expanded="true"] {{ width: 340px !important; min-width: 340px !important; }}
section[data-testid="stSidebar"] > div {{ padding-top: 1.4rem; }}
div.st-key-home_brand_btn button, div.st-key-home_brand_btn button p {{ font-size: 2.3rem !important; }}
div.st-key-home_brand_btn button {{ text-shadow: 0 0 24px rgba(76,224,255,0.35); }}
.resolvia-tagline {{ font-family: 'Manrope', sans-serif !important; font-size: 0.82rem !important; font-weight: 700 !important; letter-spacing: 0.06em !important; color: #8B90A3 !important; text-transform: none !important; margin: 4px 0 6px 0 !important; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {{ gap: 10px; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label {{
  padding: 16px 18px !important; border-radius: 16px; border: 1px solid var(--hairline); width: 100%;
  background: rgba(255,255,255,0.03); transition: all 0.2s ease; cursor: pointer;
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label p {{ font-family: 'Manrope', sans-serif !important; font-size: 1.22rem !important; font-weight: 700 !important; color: #E6E8F2 !important; }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {{ border-color: var(--accent); background: rgba(76,224,255,0.08); transform: translateX(4px); }}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) {{
  background: linear-gradient(135deg, rgba(76,224,255,0.28), rgba(167,139,250,0.20)); border-color: var(--accent);
  box-shadow: 0 0 26px -6px var(--accent), inset 0 0 0 1px rgba(76,224,255,0.35);
}}
section[data-testid="stSidebar"] [data-testid="stRadio"] label:has(input:checked) p {{ color: #FFFFFF !important; }}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p, section[data-testid="stSidebar"] .stCaption {{ font-size: 1.02rem !important; line-height: 1.5; color: #9AA0B6 !important; }}

/* readable text on the bright cyan buttons (was white on cyan) */
.stButton > button p {{ color: inherit !important; }}
.stButton > button[kind="primary"] p {{ color: #04141A !important; font-weight: 800 !important; }}
div[class*="st-key-rc_"] {{ width: 100% !important; }}
div[class*="st-key-rc_"] .stButton {{ width: 100% !important; }}
div[class*="st-key-rc_"] button {{ width: 100%; padding: 0.95rem 1rem !important; font-size: 1.05rem !important; border-radius: 14px !important; }}
.st-key-rc_approve button, .st-key-rc_mode_system button {{ animation: cta-pulse 2.2s ease-in-out infinite; }}
</style>
""", unsafe_allow_html=True)


def pill_html(label, fg, bg, icon=None, live=False):
    cls = "pill pill-live" if live else "pill"
    icon_html = f"{icon} " if icon else '<span class="pill-dot" style="background:' + fg + '"></span>'
    return f'<span class="{cls}" style="color:{fg};background:{bg};border-color:{fg}33;">{icon_html}{label}</span>'


def orchestrator_note(text):
    return f'<div class="orchestrator-note"><span class="od"></span>{text}</div>'
