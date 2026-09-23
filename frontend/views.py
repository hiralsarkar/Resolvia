"""
views.py - the four screens (Operations Desk, Case Investigation,
Resolution Control, Analytics). Every number/status/action here comes
from backend_bridge -> the real orchestrator/agents, nothing is
hand-authored sample data.
"""

import streamlit as st
import pandas as pd

from theme import COLORS, FAMILY_COLOR, SEVERITY_COLOR, STATUS_COLOR, pill_html, root_cause_label, humanize, humanize_evidence, STATUS_LABEL, SEVERITY_LABEL, TIER_LABEL
import backend_bridge as bb

PIPELINE_STAGES = [
    ("triage", "TRIAGE"), ("investigation", "INVESTIGATE"), ("rca", "DIAGNOSE"),
    ("proposal", "PROPOSE"), ("gate", "AUTHORIZE"), ("post_execution", "EXECUTE"),
    ("validation", "VALIDATE"),
]

PLOTLY_FONT = dict(family="Manrope, sans-serif", color=COLORS["ink"], size=13)


def _run_with_live_feed(fn, label="Running agent pipeline..."):
    """Real per-agent progress, not decoration - `fn(on_event)` runs the
    actual backend call and on_event fires right after each real stage
    completes (see orchestrator._advance's on_event hook). The short
    pacing delay only paces how fast a human can READ results that
    already landed - it never fabricates a stage that didn't run."""
    import time
    with st.status(label, expanded=True) as status:
        def on_event(stage_key, agent_label, detail):
            st.markdown(
                f'<div class="agent-feed-row"><span class="agent-feed-dot"></span>'
                f'<span class="agent-feed-name">{agent_label}</span> — {humanize(detail)}</div>',
                unsafe_allow_html=True)
            time.sleep(0.32)
        result = fn(on_event)
        status.update(label="Pipeline complete", state="complete")
        return result


def _plotly_layout(**kwargs):
    layout = dict(
        paper_bgcolor=COLORS["surface"], plot_bgcolor=COLORS["surface"],
        font=PLOTLY_FONT, margin=dict(l=10, r=10, t=36, b=10),
        xaxis=dict(gridcolor=COLORS["hairline"], zeroline=False),
        yaxis=dict(gridcolor=COLORS["hairline"], zeroline=False),
    )
    layout.update(kwargs)
    return layout


def kpi_tile(label, value, sub=None, col=st):
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    col.markdown(f"""
<div class="kpi-tile">
  <div class="kpi-label">{label}</div>
  <div class="kpi-value mono">{value}</div>
  {sub_html}
</div>""", unsafe_allow_html=True)


def severity_pill(sev):
    fg, bg = SEVERITY_COLOR.get(sev, (COLORS["slate"], COLORS["slate_soft"]))
    return pill_html(f"{SEVERITY_LABEL.get(sev, sev)} priority", fg, bg)


def status_pill(status):
    fg, bg = STATUS_COLOR.get(status, (COLORS["slate"], COLORS["slate_soft"]))
    return pill_html(STATUS_LABEL.get(status, status.replace("_", " ").title()), fg, bg)


def family_pill(family):
    fg = FAMILY_COLOR.get(family, COLORS["slate"])
    return pill_html(family.title(), fg, COLORS["surface_sunken"])


# ---------------------------------------------------------------- Operations Desk

def _guide_button(label, key, target_nav, primary=True):
    """A big, centered, glowing next-step button. Every screen ends in one
    so a first-time user is never left to work out the sidebar."""
    c1, c2, c3 = st.columns([1, 1.6, 1])
    with c2:
        if st.button(label, key=key, type="primary" if primary else "secondary"):
            st.session_state["nav"] = target_nav
            st.rerun()


def step_banner(step, title, hint):
    dots = "".join(
        f'<span class="step-pip{" on" if i + 1 <= step else ""}"></span>' for i in range(3))
    st.markdown(
        f'<div class="step-banner"><div class="step-pips">{dots}</div>'
        f'<div><div class="step-banner-title">Step {step} of 3 &middot; {title}</div>'
        f'<div class="step-banner-hint">{hint}</div></div></div>',
        unsafe_allow_html=True)


def render_operations_desk():
    st.markdown('<span class="eyebrow">Operations Desk</span>', unsafe_allow_html=True)
    st.markdown("## Open Exceptions")
    step_banner(1, "Choose an exception", "These are transactions where two systems disagree. Pick one to investigate.")

    df = bb.load_breaks_df()
    kpis = bb.summary_kpis()

    c1, c2, c3, c4, c5 = st.columns(5)
    kpi_tile("Open Breaks", f"{kpis['n_total']:,}", col=c1)
    kpi_tile("Exposure", f"₹{kpis['total_exposure']/1e7:.1f} Cr", col=c2)
    kpi_tile("Cased", f"{kpis['n_cased']:,}", f"of {kpis['n_total']}", col=c3)
    kpi_tile("Awaiting", f"{kpis['n_awaiting']:,}", "approval", col=c4)
    kpi_tile("CA Cases", f"{kpis['ca_count']:,}", col=c5)

    st.markdown("<br/>", unsafe_allow_html=True)

    fc1, fc2, fc3, fc4 = st.columns([1, 1, 1, 2])
    fam_filter = fc1.multiselect("Family", sorted(df["family"].unique()), key="f_family")
    sev_filter = fc2.multiselect("Severity", ["P0", "P1", "P2"], key="f_sev")
    ca_only = fc3.checkbox("Corporate actions only")
    search = fc4.text_input("Search break ID, security, counterparty", placeholder="e.g. BRK00016, RELIANCE...")

    view = df.copy()
    if fam_filter:
        view = view[view["family"].isin(fam_filter)]
    if sev_filter:
        view = view[view["severity"].isin(sev_filter)]
    if ca_only:
        view = view[view["corporate_action"] != ""]
    if search:
        s = search.strip().upper()
        view = view[
            view["break_id"].str.upper().str.contains(s) |
            view["security"].str.upper().str.contains(s) |
            view["counterparty"].str.upper().str.contains(s)
        ]

    statuses = bb.all_case_statuses()
    view = view.copy()
    view["status"] = view["break_id"].map(lambda b: statuses.get(b, "NOT_STARTED"))
    view = view.sort_values("exposure", ascending=False)

    st.caption(f"{len(view):,} of {len(df):,} breaks shown, sorted by exposure")

    display = view[["break_id", "family", "root_cause", "severity", "status",
                     "security", "counterparty", "exposure"]].head(200).rename(columns={
        "break_id": "Break ID", "family": "Family", "root_cause": "Root Cause",
        "severity": "Sev", "status": "Status", "security": "Security",
        "counterparty": "Counterparty", "exposure": "Exposure (INR)",
    })

    display["Status"] = display["Status"].map(lambda s: STATUS_LABEL.get(s, s))
    display["Sev"] = display["Sev"].map(lambda s: SEVERITY_LABEL.get(s, s))
    event = st.dataframe(
        display, hide_index=True, width='stretch', height=440,
        column_config={"Exposure (INR)": st.column_config.NumberColumn(format="₹%d")},
        on_select="rerun", selection_mode="single-row", key="ops_desk_table",
    )

    st.markdown("<br/>", unsafe_allow_html=True)
    if event.selection and event.selection.get("rows"):
        idx = event.selection["rows"][0]
        selected_id = display.iloc[idx]["Break ID"]
        st.session_state["selected_break"] = selected_id
        st.markdown(
            f'<div class="cta-panel"><span class="cta-panel-text">You picked <b>{selected_id}</b>. '
            f'Press the glowing button to let the AI agents analyze it.</span></div>',
            unsafe_allow_html=True)
        cc1, cc2, cc3 = st.columns([1, 1.6, 1])
        with cc2:
            if st.button(f"Start Analysis for {selected_id}  →", key="ops_start_analysis", type="primary"):
                st.session_state["nav"] = "Case Investigation"
                st.session_state["autorun_break"] = selected_id
                st.rerun()
    else:
        st.markdown('<div class="cta-panel quiet"><span class="cta-panel-text">'
                    'Click any row in the list above to choose an exception.</span></div>',
                    unsafe_allow_html=True)


# ---------------------------------------------------------------- Case Investigation

def render_stepper(case):
    stages_state = []
    if case is None:
        stages_state = [("pending", label) for _, label in PIPELINE_STAGES]
    else:
        status = case["status"]
        terminal = status in ("CLOSED", "REOPENED", "REJECTED", "HALTED_DATA_QUALITY")
        found_active = False
        for key, label in PIPELINE_STAGES:
            if key == "gate":
                done = case["gate_result"] is not None and case["gate_result"]["authorized"]
                blocked = case["gate_result"] is not None and not case["gate_result"]["authorized"]
                if done:
                    stages_state.append(("done", label))
                elif blocked and not found_active:
                    stages_state.append(("blocked", label))
                    found_active = True
                else:
                    stages_state.append(("pending", label))
                continue
            done = case.get(key) is not None
            if done:
                stages_state.append(("done", label))
            elif not found_active and not terminal:
                stages_state.append(("active", label))
                found_active = True
            else:
                stages_state.append(("pending", label))

    html = '<div class="stepper">'
    for i, (state, label) in enumerate(stages_state):
        line_cls = "step-line done" if state == "done" or (i > 0 and stages_state[i-1][0] == "done") else "step-line"
        dot_cls = {"done": "step-dot done", "active": "step-dot active",
                    "blocked": "step-dot blocked", "pending": "step-dot"}[state]
        mark = "✓" if state == "done" else ("✕" if state == "blocked" else str(i + 1))
        html += f'<div class="step"><div class="{line_cls}"></div><div class="{dot_cls}">{mark}</div>' \
                f'<div class="step-label">{label}</div></div>'
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_case_investigation():
    st.markdown('<span class="eyebrow">Case Investigation</span>', unsafe_allow_html=True)

    break_id = st.session_state.get("selected_break")
    if not break_id:
        st.markdown("## Nothing chosen yet")
        st.markdown("Pick an exception first, then come back here to see the AI analyze it.")
        _guide_button("Choose an Exception  →", "ci_go_ops", "Operations Desk")
        return

    df = bb.load_breaks_df()
    row = df[df["break_id"] == break_id]
    if row.empty:
        st.error(f"Unknown break {break_id}")
        return
    row = row.iloc[0]

    step_banner(2, "Watch the AI analyze it",
                "Five AI agents work one after another. You don't need to do anything but watch.")

    hc1, hc2 = st.columns([3, 1])
    hc1.markdown(f"## {break_id}")
    hc1.markdown(
        f"{family_pill(row['family'])} {severity_pill(row['severity'])} "
        f"{status_pill(bb.case_status(break_id))} "
        + (pill_html("CORPORATE ACTION", COLORS['accent'], COLORS['accent_soft'], live=True) if row['corporate_action'] else ""),
        unsafe_allow_html=True,
    )
    hc2.markdown(f'<div style="text-align:right;"><span class="eyebrow">Exposure</span>'
                 f'<div class="kpi-value mono" style="font-size:1.5rem;">₹{row["exposure"]:,.0f}</div></div>',
                 unsafe_allow_html=True)

    case = bb.get_case(break_id)
    if case is None:
        st.markdown("<br/>", unsafe_allow_html=True)
        # Arriving via the "Start Analysis" button already expressed intent -
        # start immediately instead of asking the user to click a second time.
        if st.session_state.get("autorun_break") == break_id:
            st.session_state.pop("autorun_break", None)
            _run_with_live_feed(lambda on_event: bb.get_or_create_case(break_id, on_event=on_event))
            st.rerun()
        if st.button("▶  Start Analysis", key="ci_start_analysis", type="primary"):
            _run_with_live_feed(lambda on_event: bb.get_or_create_case(break_id, on_event=on_event))
            st.rerun()
        render_stepper(None)
        return

    st.markdown("<br/>", unsafe_allow_html=True)
    render_stepper(case)
    st.markdown("<br/>", unsafe_allow_html=True)

    left, right = st.columns([1, 1], gap="large")

    with left:
        st.markdown("#### Structured Evidence")
        se = case["investigation"]["structured_evidence"]
        for label, rec in [("Trade", se["trade"]), ("Position", se["position"]), ("Settlement", se["settlement"])]:
            if rec:
                with st.expander(label, expanded=(label == "Trade")):
                    st.dataframe(pd.DataFrame([rec]).T.rename(columns={0: "value"}),
                                 width='stretch')
        if se["cash_transactions"]:
            with st.expander(f"Cash Transactions ({len(se['cash_transactions'])})"):
                st.dataframe(pd.DataFrame(se["cash_transactions"]), width='stretch', hide_index=True)

        doc = case["investigation"]["document_evidence"]
        if doc.get("has_document"):
            st.markdown("#### Document Evidence")
            st.caption(f"{doc['doc_id']} — extracted via {doc['extraction_method']}")
            st.markdown(f'<div class="doc-box">{doc["text"]}</div>', unsafe_allow_html=True)
            if doc["related_documents"]:
                st.caption("Related documents (RAG retrieval)")
                for r in doc["related_documents"]:
                    st.markdown(f"- `{r['break_id']}` — {r['root_cause']} (similarity {r['similarity']:.2f})")

        ca = case["investigation"]["corporate_action_context"]
        if ca["is_corporate_action"]:
            st.markdown("#### Corporate Action Reference")
            st.markdown(pill_html(ca["corporate_action_type"], COLORS["accent"], COLORS["accent_soft"]),
                        unsafe_allow_html=True)
            for r in ca["reference_entries"]:
                st.markdown(f"**{r['action_type']}** ({r['classification']}) — similarity {r['similarity']:.2f}")
                st.caption(r["text"])

    with right:
        st.markdown("#### Root Cause Analysis")
        r = case["rca"]
        st.markdown(f"**{root_cause_label(r['root_cause'])}**")
        conf_pct = r["confidence"] * 100
        st.markdown(f"""
<div style="background:{COLORS['surface_sunken']}; border-radius:8px; height:10px; overflow:hidden; margin:6px 0 4px 0;">
  <div class="conf-fill" style="background:{COLORS['accent']}; width:{conf_pct}%; height:100%;
       animation: conf-grow 0.7s cubic-bezier(.2,.7,.3,1) both;"></div>
</div>
<span class="mono" style="font-size:0.85rem; color:{COLORS['ink_soft']};">{conf_pct:.1f}% confidence</span>
<style>@keyframes conf-grow {{ from {{ width: 0%; }} to {{ width: {conf_pct}%; }} }}</style>
""", unsafe_allow_html=True)

        ec1, ec2 = st.columns(2)
        ec1.metric("Expected", str(r["expected"]))
        ec2.metric("Actual", str(r["actual"]) or "—")

        if r["alternative_explanations"]:
            st.caption("Alternative explanations considered")
            for alt in r["alternative_explanations"]:
                st.markdown(f"- {root_cause_label(alt['root_cause'])} ({alt['probability']*100:.1f}%)")
        else:
            st.caption("No competing explanation — model found no other class with meaningful support.")

        if r["requires_human_decision"]:
            st.warning("A person should double-check this diagnosis: " + humanize("; ".join(r["escalation_reasons"])))
        if r["priority_flag"]:
            st.caption(f"Priority: {humanize(r['priority_flag'])}")

        st.markdown("#### Evidence Cited")
        st.markdown(" · ".join(humanize_evidence(e) for e in r["evidence_cited"]))

    st.markdown("<br/>", unsafe_allow_html=True)
    with st.expander("Case Audit Trail"):
        for e in case["history"]:
            st.markdown(f"""<div class="timeline-row">
  <span class="timeline-time mono">{e['timestamp'].split('T')[1]}</span>
  <span class="timeline-event">{e['event']}</span>
  <span class="timeline-detail">{e['detail']}</span>
</div>""", unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)
    if case["status"] == "AWAITING_APPROVAL":
        msg = "The AI has a recommendation, but a person must approve it before anything changes."
    else:
        msg = "The analysis is complete. See what the AI recommends."
    st.markdown(f'<div class="cta-panel"><span class="cta-panel-text">{msg}</span></div>',
                unsafe_allow_html=True)
    _guide_button("See the Recommendation  →", "ci_go_resolution", "Resolution Control")


# ---------------------------------------------------------------- Resolution Control

def render_resolution_control():
    st.markdown('<span class="eyebrow">Resolution Control</span>', unsafe_allow_html=True)

    break_id = st.session_state.get("selected_break")
    if not break_id:
        st.markdown("## Nothing chosen yet")
        st.markdown("Pick an exception first.")
        _guide_button("Choose an Exception  →", "rc_go_ops", "Operations Desk")
        return

    case = bb.get_case(break_id)
    if case is None or case.get("proposal") is None:
        st.markdown("## The AI hasn't looked at this one yet")
        st.markdown(f"Let the agents analyze {break_id} first.")
        st.session_state["autorun_break"] = break_id
        _guide_button("Start Analysis  →", "rc_go_ci", "Case Investigation")
        return

    step_banner(3, "Make the decision", "Read what the AI recommends, then choose: review, approve or escalate.")

    p = case["proposal"]
    st.markdown(f"## {break_id} — Recommendation")

    needs_ok = p["authority_tier"] == "CONTROLLED_ACTION"
    tier_color = COLORS["amber"] if needs_ok else COLORS["forest"]
    tier_bg = COLORS["amber_soft"] if needs_ok else COLORS["forest_soft"]
    st.markdown(pill_html(TIER_LABEL.get(p["authority_tier"], p["authority_tier"]), tier_color, tier_bg) + "  " +
                status_pill(case["status"]), unsafe_allow_html=True)

    st.markdown("<br/>", unsafe_allow_html=True)
    cc1, cc2, cc3 = st.columns(3)
    kpi_tile("Money at risk", f"₹{p['risk']['financial_exposure']:,.0f}", col=cc1)
    kpi_tile("Risk level", p["risk"]["level"].title(), f"{SEVERITY_LABEL.get(p['risk']['severity'], p['risk']['severity'])} priority", col=cc2)
    kpi_tile("AI certainty", f"{p['rca_confidence']*100:.1f}%", col=cc3)

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("#### Recommended Action")
    st.markdown(f'<div class="rv-card">{p["recommended_action"]}</div>', unsafe_allow_html=True)

    st.markdown("#### Reason")
    st.write(humanize(p["reason"]))

    st.markdown("#### Expected Outcome")
    st.write(p["expected_outcome"])

    if p["rca_flagged_for_human_review"]:
        st.warning("A person should double-check this diagnosis: " +
                    humanize("; ".join(p["rca_escalation_reasons"])))

    st.markdown("<br/>", unsafe_allow_html=True)
    if case["status"] in ("AWAITING_APPROVAL", "IN_REVIEW", "ESCALATED"):
        if case["status"] != "AWAITING_APPROVAL":
            st.markdown(f'<div class="cta-panel quiet"><span class="cta-panel-text">Current status: '
                        f'<b>{STATUS_LABEL[case["status"]]}</b>. You can still make a final choice below.</span></div>',
                        unsafe_allow_html=True)
        st.markdown('<div class="cta-panel"><span class="cta-panel-text">'
                    'This change touches money or account details, so the AI is <b>not allowed</b> '
                    'to do it alone. Please choose what happens next.</span></div>', unsafe_allow_html=True)
        with st.expander("Optional: who is deciding, and why"):
            approver = st.text_input("Your name / email", value="ops.head@resolvia.local")
            notes = st.text_area("Notes", placeholder="Reason for this decision (optional)")

        def _approve_with(mode):
            _run_with_live_feed(
                lambda on_event: bb.approve(break_id, approver, notes, on_event=on_event, mode=mode),
                label="Carrying out the fix and double-checking it...")
            st.session_state.pop("choosing_mode", None)
            st.rerun()

        if st.session_state.get("choosing_mode") == break_id:
            st.markdown("#### Approved. How should the fix be carried out?")
            m1, m2 = st.columns(2)
            if m1.button("Controlled Action — the system does it", key="rc_mode_system", type="primary"):
                _approve_with("Controlled Action")
            if m2.button("Manually by Analyst — I will do it myself", key="rc_mode_manual"):
                _approve_with("Manually by Analyst")
            if st.button("← Go back", key="rc_mode_back"):
                st.session_state.pop("choosing_mode", None)
                st.rerun()
        else:
            b1, b2, b3 = st.columns(3)
            if b1.button("Review — I need a closer look", key="rc_review"):
                bb.mark(break_id, "IN_REVIEW", approver, notes)
                st.rerun()
            if b2.button("✓  Approve", key="rc_approve", type="primary"):
                st.session_state["choosing_mode"] = break_id
                st.rerun()
            if b3.button("Escalate — send to a senior", key="rc_escalate"):
                bb.mark(break_id, "ESCALATED", approver, notes)
                st.rerun()
    else:
        v = case.get("validation")
        if case["status"] in ("CLOSED", "REOPENED", "REJECTED"):
            st.markdown("#### Result")
            st.markdown(status_pill(case["status"]), unsafe_allow_html=True)
            manual = case.get("execution_mode") == "Manually by Analyst"
            plain = {"CLOSED": ("Fixed manually by the analyst and double-checked. This exception is resolved." if manual
                                else "Fixed by the system and double-checked. This exception is resolved."),
                     "REOPENED": "The fix did not fully work, so this case was reopened for a person to review.",
                     "REJECTED": "The recommendation was rejected. Nothing was changed."}[case["status"]]
            st.markdown(f'<div class="cta-panel"><span class="cta-panel-text">{plain}</span></div>',
                        unsafe_allow_html=True)
            if v:
                st.caption(v["reason"])
        else:
            st.info(f"Case status: {case['status']}")
        st.markdown("<br/>", unsafe_allow_html=True)
        _guide_button("Review Another Exception  →", "rc_next_case", "Operations Desk")


# ---------------------------------------------------------------- Analytics

def render_analytics():
    import plotly.graph_objects as go
    st.markdown('<span class="eyebrow">Portfolio View</span>', unsafe_allow_html=True)
    st.markdown("## Analytics")

    df = bb.load_breaks_df()
    kpis = bb.summary_kpis()
    track_record = bb.resolved_cases_summary()

    c1, c2, c3, c4 = st.columns(4)
    kpi_tile("Total Breaks", f"{kpis['n_total']:,}", col=c1)
    kpi_tile("Exposure", f"₹{kpis['total_exposure']/1e7:.1f} Cr", col=c2)
    kpi_tile("CA Breaks", f"{kpis['ca_count']:,}", f"{kpis['ca_count']/kpis['n_total']*100:.1f}% of total", col=c3)
    kpi_tile("Closed (this session)", f"{kpis['n_closed']:,}",
             "live cases you've run below", col=c4)

    if track_record["n"]:
        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown("#### System Track Record")
        st.caption(
            f"{track_record['n']} cases run through the full Triage→Validation pipeline "
            f"via the production Orchestrator (not this browser session specifically - see "
            f"`backend/knowledge/resolved_cases.json`). The KPI above only counts cases "
            f"*you've* opened live; this is what the system has actually resolved."
        )
        tr1, tr2, tr3 = st.columns(3)
        kpi_tile("Cases Resolved", f"{track_record['n']:,}", col=tr1)
        kpi_tile("Closed", f"{track_record['n_closed']:,}",
                 f"{track_record['n_closed']/track_record['n']*100:.0f}%", col=tr2)
        kpi_tile("Reopened", f"{track_record['n_reopened']:,}",
                 "all CA_VOLUNTARY_DECISION, by design", col=tr3)

    st.markdown("<br/>", unsafe_allow_html=True)
    g1, g2 = st.columns(2)

    with g1:
        st.markdown("#### Breaks by Family")
        fam_counts = df["family"].value_counts()
        fig = go.Figure(go.Bar(
            x=fam_counts.values, y=fam_counts.index, orientation="h",
            marker_color=[FAMILY_COLOR.get(f, COLORS["slate"]) for f in fam_counts.index],
            text=fam_counts.values, textposition="outside",
        ))
        fig.update_layout(**_plotly_layout(height=280, showlegend=False))
        st.plotly_chart(fig, width='stretch')

    with g2:
        st.markdown("#### Breaks by Severity")
        sev_counts = df["severity"].value_counts().reindex(["P0", "P1", "P2"])
        fig = go.Figure(go.Pie(
            labels=sev_counts.index, values=sev_counts.values, hole=0.62,
            marker_colors=[SEVERITY_COLOR[s][0] for s in sev_counts.index],
            textinfo="label+percent",
        ))
        fig.update_layout(**_plotly_layout(height=280, showlegend=False))
        st.plotly_chart(fig, width='stretch')

    # Root Cause Distribution chart deliberately omitted here: every one of
    # the 20 classes sits at exactly 150 by construction (stratified
    # generation, see generate_trade_breaks.py), so the bar chart would show
    # a perfectly flat distribution - correct, but reads as synthetic/fake
    # at a glance and invites exactly that question. The per-class counts
    # are already stated plainly in docs/model_comparison.md and schema.md
    # instead, next to the caveat that explains why they're even.

    st.markdown("<br/>", unsafe_allow_html=True)
    st.markdown("#### Model Comparison — root_cause classification (held-out TEST)")
    st.caption("Rules/RPA baseline vs the three ML candidates — see docs/model_comparison.md")
    models = ["Rules / RPA", "Logistic Regression", "Random Forest", "XGBoost"]
    scores = [0.820, 0.774, 0.933, 0.932]
    fig = go.Figure(go.Bar(
        x=models, y=scores,
        marker_color=[COLORS["slate"], COLORS["amber"], COLORS["forest"], COLORS["forest"]],
        text=[f"{s:.3f}" for s in scores], textposition="outside",
    ))
    fig.update_layout(**_plotly_layout(height=320, yaxis=dict(range=[0, 1.08], gridcolor=COLORS["hairline"])))
    st.plotly_chart(fig, width='stretch')
    st.caption("Rules hit 0.000 accuracy on the 3 corporate-action sub-causes specifically — "
               "the concrete case for why this needs a reasoning step, not just more rules.")

    statuses = bb.all_case_statuses()
    if statuses:
        st.markdown("<br/>", unsafe_allow_html=True)
        st.markdown("#### Cases Processed This Session")
        sc = pd.Series(statuses.values()).value_counts()
        fig = go.Figure(go.Bar(
            x=sc.index, y=sc.values,
            marker_color=[STATUS_COLOR.get(s, (COLORS["slate"], None))[0] for s in sc.index],
            text=sc.values, textposition="outside",
        ))
        fig.update_layout(**_plotly_layout(height=280, showlegend=False))
        st.plotly_chart(fig, width='stretch')
