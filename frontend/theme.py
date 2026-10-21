"""
Colours, labels and global CSS for the app.

The app uses the same look as the landing animation so the two feel like one
product: dark surfaces, Bricolage Grotesque, Manrope and JetBrains Mono, and
colour that always means something. Cyan is data and detection, violet is AI
reasoning, magenta is a recommendation, amber is waiting on a person, and
green is verified.
"""

COLORS = {
    "bone": "#0A0B10",           # page background
    "surface": "#12141D",        # raised card
    "surface_sunken": "#171A25", # recessed panel
    "ink": "#F2F3F8",            # primary text (near-white on dark)
    "ink_soft": "#8B90A3",       # secondary text
    "ink_faint": "#565B6E",      # tertiary text
    "hairline": "#232733",

    "accent": "#4CE0FF",         # cyan, the default interactive colour
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
    "TRADE": COLORS["violet"],
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
    "ON_HOLD": (COLORS["amber"], COLORS["amber_soft"]),
}

# Plain names for the 20 root-cause keys, used wherever a person reads them
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
    "HALTED_DATA_QUALITY": "Stopped: data problem", "ON_HOLD": "On hold for client election", "IN_REVIEW": "In review", "ESCALATED": "Escalated to senior", "CASE_CREATED": "Started",
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


# Line icons, drawn on a 24px grid. Used for page headers and the sidebar.
ICONS = {
    "architecture": '<circle cx="12" cy="12" r="3"/><circle cx="4.5" cy="5" r="2"/><circle cx="19.5" cy="5" r="2"/><circle cx="4.5" cy="19" r="2"/><circle cx="19.5" cy="19" r="2"/><path d="M6 6.5 9.8 10M18 6.5 14.2 10M6 17.5l3.8-3.5M18 17.5 14.2 14"/>',
    "home": '<path d="M3 11 12 4l9 7"/><path d="M5 10v10h14V10"/><path d="M10 20v-6h4v6"/>',
    "queue": '<path d="M8 6h13M8 12h13M8 18h13"/><circle cx="4" cy="6" r="1.3"/><circle cx="4" cy="12" r="1.3"/><circle cx="4" cy="18" r="1.3"/>',
    "case": '<circle cx="11" cy="11" r="7"/><path d="m20 20-4-4"/><path d="M8 11h6M11 8v6"/>',
    "resolution": '<path d="M14.7 6.3a4 4 0 0 0 5 5L13 18l-3 3-4-4 3-3 6.7-6.7a4 4 0 0 0-1-1z"/>',
    "guide": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2V5z"/><path d="M4 19a2 2 0 0 1 2-2h13"/><path d="M9 7h6"/>',
    "audit": '<path d="M12 3 4 6v6c0 4.4 3.4 7.9 8 9 4.6-1.1 8-4.6 8-9V6l-8-3z"/><path d="m9 12 2 2 4-4"/>',
    "manager": '<path d="M4 20V10M10 20V4M16 20v-8M22 20H2"/>',
}
NAV_ICONS = [("architecture", "accent"), ("home", "forest"), ("queue", "amber"), ("case", "violet"),
             ("resolution", "magenta"), ("guide", "accent"), ("audit", "forest"), ("manager", "violet")]


def icon_svg(name, color, size=22):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="{color}" stroke-width="1.8" '
            f'stroke-linecap="round" stroke-linejoin="round">{ICONS[name]}</svg>')


def page_header(icon, eyebrow, title, sub="", color=None):
    """The header every page shares: a glowing icon tile, the title, and a flow line."""
    import streamlit as st
    color = color or COLORS["accent"]
    st.markdown(
        f'<div class="ph-hero" style="--c:{color}"><div class="ph-icon">{icon_svg(icon, color, 26)}</div>'
        f'<div class="ph-text"><span class="eyebrow" style="color:{color} !important">{eyebrow}</span>'
        f'<div class="ph-title">{title}</div>' + (f'<div class="ph-sub">{sub}</div>' if sub else "") + '</div></div>'
        f'<div class="flowline" style="--c:{color}"><span></span></div>', unsafe_allow_html=True)


def _nav_icon_css():
    from urllib.parse import quote
    rules = []
    for i, (name, key) in enumerate(NAV_ICONS, start=1):
        c = COLORS[key]
        uri = quote(icon_svg(name, c, 24))
        rules.append(
            f'section[data-testid="stSidebar"] [role="radiogroup"] label:nth-of-type({i}) [data-testid="stMarkdownContainer"] p::before '
            f'{{ background: url("data:image/svg+xml;utf8,{uri}") center/19px no-repeat, {c}1F; border-color: {c}66; box-shadow: 0 0 16px -5px {c}; }}')
    return "\n".join(rules)


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

/* ---------- elite layer: icons, glow and flow everywhere ---------- */
.ph-hero {{ display: flex; align-items: center; gap: 18px; margin: 2px 0 6px; animation: feed-in .5s ease both; }}
.ph-icon {{ width: 58px; height: 58px; border-radius: 17px; display: grid; place-items: center; flex-shrink: 0;
  background: color-mix(in srgb, var(--c) 13%, transparent); border: 1px solid color-mix(in srgb, var(--c) 50%, transparent);
  box-shadow: 0 0 30px -8px var(--c), inset 0 0 18px -10px var(--c); animation: icon-breathe 3.2s ease-in-out infinite; }}
.ph-icon svg {{ filter: drop-shadow(0 0 5px var(--c)); }}
@keyframes icon-breathe {{ 50% {{ box-shadow: 0 0 42px -6px var(--c), inset 0 0 20px -10px var(--c); }} }}
.ph-title {{ font-family: 'Bricolage Grotesque', sans-serif; font-weight: 800; font-size: 2.2rem; letter-spacing: -0.04em; line-height: 1.05;
  background: linear-gradient(90deg, #FFFFFF 30%, var(--c)); -webkit-background-clip: text; background-clip: text; color: transparent !important; }}
.ph-sub {{ color: var(--ink-soft) !important; font-size: 0.95rem; margin-top: 4px; }}
.flowline {{ position: relative; height: 2px; margin: 14px 0 22px; border-radius: 2px;
  background: linear-gradient(90deg, var(--c), color-mix(in srgb, var(--c) 10%, transparent) 70%, transparent); opacity: .8; overflow: visible; }}
.flowline span {{ position: absolute; top: -4px; left: 0; width: 10px; height: 10px; border-radius: 50%; background: #fff;
  box-shadow: 0 0 10px #fff, 0 0 22px var(--c); animation: flow-run 4.5s cubic-bezier(.45,0,.55,1) infinite; }}
@keyframes flow-run {{ 0% {{ left: 0; opacity: 0; }} 10% {{ opacity: 1; }} 85% {{ opacity: 1; }} 100% {{ left: 70%; opacity: 0; }} }}

.section-h {{ display: flex; align-items: center; gap: 10px; margin: 26px 0 12px; font-family: 'Bricolage Grotesque', sans-serif;
  font-weight: 800; font-size: 1.3rem; letter-spacing: -0.02em; color: var(--ink); }}
.section-dot {{ width: 10px; height: 10px; border-radius: 50%; background: var(--c); box-shadow: 0 0 12px var(--c); animation: pulse-dot 1.8s ease-in-out infinite; }}
.glow-id {{ color: var(--accent) !important; font-weight: 700; text-shadow: 0 0 12px rgba(76,224,255,.45); }}
.stMarkdown h3 {{ position: relative; padding-left: 16px; }}
.stMarkdown h3::before {{ content: ""; position: absolute; left: 0; top: 18%; bottom: 18%; width: 4px; border-radius: 4px;
  background: linear-gradient(180deg, var(--accent), var(--violet)); box-shadow: 0 0 12px var(--accent); }}

/* cards across the app pick up a glass look with a coloured glow on hover */
.stApp .wb-card, .stApp .wb-card-tight, .stApp .wb-action, .stApp .rc-card, .stApp .rc-next, .stApp .rc-step, .stApp .rv-card, .stApp .kpi-tile {{
  background: radial-gradient(120% 90% at 0% 0%, rgba(76,224,255,.06), transparent 55%), linear-gradient(160deg, rgba(255,255,255,.04), rgba(255,255,255,.01)) !important;
  border: 1px solid #262B3A !important; position: relative; overflow: hidden;
  transition: transform .25s ease, box-shadow .25s ease, border-color .25s ease !important; }}
.stApp .wb-card:hover, .stApp .wb-card-tight:hover, .stApp .wb-action:hover, .stApp .rc-card:hover, .stApp .rc-next:hover, .stApp .rv-card:hover {{
  border-color: rgba(76,224,255,.5) !important; box-shadow: 0 0 36px -16px var(--accent); transform: translateY(-2px); }}
.stApp .wb-card-tight::before, .stApp .rc-next::before {{ content: ""; position: absolute; left: 0; right: 0; top: 0; height: 2px;
  background: linear-gradient(90deg, var(--accent), var(--violet)); box-shadow: 0 0 10px var(--accent); }}
.stApp .rc-next {{ border-color: rgba(76,224,255,.35) !important; box-shadow: 0 0 34px -18px var(--accent); }}
.stApp div[data-testid="column"]:nth-child(2) .wb-card-tight::before {{ background: linear-gradient(90deg, var(--signal), var(--amber)); box-shadow: 0 0 10px var(--signal); }}
.stApp div[data-testid="column"]:nth-child(3) .wb-card-tight::before {{ background: linear-gradient(90deg, var(--amber), var(--magenta)); box-shadow: 0 0 10px var(--amber); }}
.stApp div[data-testid="column"]:nth-child(4) .wb-card-tight::before {{ background: linear-gradient(90deg, var(--violet), var(--forest)); box-shadow: 0 0 10px var(--violet); }}
.stApp .wb-big, .stApp .rc-big {{ text-shadow: 0 0 18px rgba(76,224,255,.25); }}
.stApp .wb-label, .stApp .rc-label {{ color: var(--accent) !important; letter-spacing: .12em; }}
.stApp .wb-title, .stApp .rc-title {{ background: linear-gradient(90deg, #FFFFFF 35%, var(--accent)); -webkit-background-clip: text; background-clip: text; color: transparent !important; }}
.stApp .wb-event:before {{ animation: pulse-dot 2s ease-in-out infinite; }}

/* tables, expanders and inputs glow on focus */
[data-testid="stDataFrame"] {{ box-shadow: 0 0 34px -20px var(--accent); border-color: #262B3A !important; }}
[data-testid="stExpander"] {{ border: 1px solid #262B3A !important; }}
[data-testid="stExpander"]:hover {{ border-color: rgba(167,139,250,.5) !important; box-shadow: 0 0 30px -18px var(--violet); }}
.stTextInput input:focus, .stTextArea textarea:focus {{ border-color: var(--accent) !important; box-shadow: 0 0 0 1px var(--accent), 0 0 18px -6px var(--accent) !important; }}
[data-testid="stFileUploaderDropzone"] {{ background: rgba(255,255,255,.02) !important; border: 1px dashed rgba(76,224,255,.35) !important; border-radius: 14px !important; }}
.stButton > button {{ box-shadow: 0 0 16px -8px var(--accent); }}

/* sidebar navigation: an icon tile per page */
section[data-testid="stSidebar"] [role="radiogroup"] label > div > div:first-child:not([data-testid]) {{ display: none !important; }}
section[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p {{ display: flex !important; align-items: center; gap: 14px; }}
section[data-testid="stSidebar"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] p::before {{
  content: ""; width: 38px; height: 38px; flex-shrink: 0; border-radius: 11px; border: 1px solid transparent; }}
section[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) [data-testid="stMarkdownContainer"] p::before {{ animation: icon-breathe 2.6s ease-in-out infinite; --c: var(--accent); }}
{_nav_icon_css()}
</style>
""", unsafe_allow_html=True)


def pill_html(label, fg, bg, icon=None, live=False):
    cls = "pill pill-live" if live else "pill"
    icon_html = f"{icon} " if icon else '<span class="pill-dot" style="background:' + fg + '"></span>'
    return f'<span class="{cls}" style="color:{fg};background:{bg};border-color:{fg}33;">{icon_html}{label}</span>'


def orchestrator_note(text):
    return f'<div class="orchestrator-note"><span class="od"></span>{text}</div>'
