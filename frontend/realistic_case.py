"""Human-first case and resolution workflow.

The analyst flow is deliberately ordered as:
Review -> Understand -> Read Guide -> Choose method -> Act -> Verify -> Close.
Choosing Manual never closes a case and never counts as approval.
"""
import streamlit as st
import pandas as pd
import backend_bridge as bb
from theme import STATUS_LABEL, SEVERITY_LABEL, root_cause_label


def status_label(value):
    return STATUS_LABEL.get(value, str(value).replace("_", " ").title())


def row_for(bid):
    df = bb.load_breaks_df()
    rows = df[df.break_id == bid]
    return rows.iloc[0] if not rows.empty else None


def go(page):
    st.session_state["nav"] = page
    st.rerun()


def audit(bid):
    st.session_state["selected_break"] = bid
    st.session_state["audit_break_filter"] = bid
    bb.audit("CASE_AUDIT_OPENED", bid, "Operator opened the audit history for this break")
    go("Audit Trail")


def css():
    st.markdown("""<style>
    .rc-title{font-size:2.15rem;font-weight:800;letter-spacing:-.04em;margin:0}
    .rc-sub{color:#8b90a3;margin:.25rem 0 1.2rem}
    .rc-card{background:#12141d;border:1px solid #272d3b;border-radius:16px;padding:20px;margin:0 0 14px}
    .rc-next{background:#151b25;border:1px solid #3a4b60;border-radius:16px;padding:22px;margin:14px 0}
    .rc-label{font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:#8b90a3;font-weight:800}
    .rc-big{font-size:1.8rem;font-weight:800}
    .rc-muted{color:#8b90a3;font-size:.84rem}
    .rc-step{border-left:3px solid #354052;padding:5px 0 5px 14px;margin:9px 0}
    .rc-step strong{display:block}
    div[data-testid="stButton"]>button{min-height:45px;border-radius:10px;font-weight:750}
    </style>""", unsafe_allow_html=True)


def case_audit(bid):
    events = bb.audit_events(break_id=bid, limit=100)
    if not events:
        st.caption("No activity recorded yet.")
        return
    rows = []
    for e in events:
        rows.append({
            "Time": pd.to_datetime(e["timestamp"], utc=True).strftime("%d %b %Y · %H:%M UTC"),
            "Operations ID": e.get("actor_id", "SYSTEM"),
            "Action": e.get("action", ""),
            "What was done": e.get("detail", ""),
        })
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch", height=300)


def render_case():
    css()
    bid = st.session_state.get("selected_break")
    if not bid:
        st.info("Choose a break from the Break Queue first.")
        return
    row = row_for(bid)
    if row is None:
        st.error("Break not found.")
        return
    case = bb.get_case(bid)
    st.markdown(f'<div class="rc-title">{bid}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rc-sub">{root_cause_label(row.root_cause_key)} · {row.counterparty}</div>', unsafe_allow_html=True)

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Priority", SEVERITY_LABEL.get(row.severity, row.severity))
    c2.metric("Exposure", f"₹{row.exposure:,.0f}")
    c3.metric("Status", status_label(case.get("status", "NOT_STARTED")) if case else "Not started")
    c4.metric("Operations ID", st.session_state.get("operator_id", "OPS-1047"))

    if case is None:
        st.markdown('<div class="rc-next"><div class="rc-label">First step</div><div class="rc-big">Understand the break</div><div class="rc-muted">Resolvia will review the available evidence and prepare the case. No correction is made during analysis.</div></div>', unsafe_allow_html=True)
        if st.button("Start case review →", type="primary", use_container_width=True, key="real_start"):
            with st.status("Reviewing case", expanded=True) as s:
                bb.get_or_create_case(bid, on_event=lambda stage, label, detail: st.write(f"{label}: {detail}"))
                s.update(label="Review complete", state="complete")
            st.rerun()
        return

    status = case.get("status", "CASE_CREATED")
    rca = case.get("rca") or {}
    proposal = case.get("proposal") or {}
    investigation = case.get("investigation") or {}
    triage = case.get("triage") or {}

    st.markdown('<div class="rc-card"><div class="rc-label">What happened</div><h3>' + root_cause_label(rca.get("root_cause", row.root_cause_key)) + '</h3><div class="rc-muted">' + str(rca.get("explanation", "")) + '</div></div>', unsafe_allow_html=True)

    with st.expander("See evidence used for the analysis", expanded=False):
        st.json(investigation.get("structured_evidence", {}))
        if investigation.get("document_evidence", {}).get("has_document"):
            st.write(investigation["document_evidence"].get("text", ""))

    if proposal:
        st.markdown(f'<div class="rc-card"><div class="rc-label">Recommended resolution</div><h3>{proposal.get("recommended_action", "")}</h3><div class="rc-muted">{proposal.get("reason", "")}</div><br><b>Owner:</b> {triage.get("route", "Operations")}</div>', unsafe_allow_html=True)

    if status in {"CASE_CREATED", "IN_REVIEW", "AWAITING_APPROVAL"}:
        st.markdown('<div class="rc-next"><div class="rc-label">Next step</div><div class="rc-big">Read the Resolution Guide</div><div class="rc-muted">Before choosing a resolution method, review who owns the correction, what must be checked, which evidence is required, and when to escalate.</div></div>', unsafe_allow_html=True)
        if st.button("Read Resolution Guide →", type="primary", use_container_width=True, key="real_read_guide"):
            bb.audit("RESOLUTION_GUIDE_OPENED", bid, "Analyst opened the manual resolution guide")
            go("Resolution Playbook")
    elif status == "MANUAL_IN_PROGRESS":
        st.markdown('<div class="rc-next"><div class="rc-label">Manual action in progress</div><div class="rc-big">Break remains OPEN</div><div class="rc-muted">The analyst selected manual resolution. Perform the correction in the appropriate operational system, then return to record exactly what was done.</div></div>', unsafe_allow_html=True)
        if st.button("Record manual action →", type="primary", use_container_width=True, key="real_record_manual"):
            go("Resolution Control")
    elif status == "AWAITING_VERIFICATION":
        st.markdown('<div class="rc-next"><div class="rc-label">Awaiting verification</div><div class="rc-big">Do not close yet</div><div class="rc-muted">The manual action is recorded. A separate verification step is required before closure.</div></div>', unsafe_allow_html=True)
        if st.button("Verify manual resolution →", type="primary", use_container_width=True, key="real_verify"):
            go("Resolution Control")
    elif status == "CLOSED":
        st.success("Resolved and verified. This case is closed.")
    elif status == "ESCALATED":
        st.warning("Escalated. The break remains open until the receiving owner resolves or reassigns it.")

    st.markdown("### Case history")
    case_audit(bid)
    a, b = st.columns(2)
    if a.button("Resolution workspace", use_container_width=True, key="real_res"):
        go("Resolution Control")
    if b.button("View full audit →", use_container_width=True, key="real_audit"):
        audit(bid)


def render_guide():
    css()
    bid = st.session_state.get("selected_break")
    if not bid:
        st.info("Choose a break first.")
        return
    case = bb.get_case(bid)
    row = row_for(bid)
    if not case:
        st.warning("Complete the case review before opening the guide.")
        return
    root = (case.get("rca") or {}).get("root_cause", row.root_cause_key)
    views = __import__("operational_views")
    playbooks = getattr(views, "PLAYBOOKS", {})
    default = getattr(views, "DEFAULT_PLAYBOOK")
    owner, escalation, reason, evidence, steps, do_not = playbooks.get(root, default)

    st.markdown(f'<div class="rc-title">Resolution Guide · {bid}</div>', unsafe_allow_html=True)
    st.markdown('<div class="rc-sub">Understand the correction first. Choose how to perform it only after reading this guide.</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rc-card"><div class="rc-label">Owner</div><h3>{owner}</h3><div class="rc-muted">Escalation: {escalation}</div><p>{reason}</p></div>', unsafe_allow_html=True)
    st.markdown("### Do this in order")
    for i, step in enumerate(steps, 1):
        st.markdown(f'<div class="rc-step"><strong>{i}. {step}</strong></div>', unsafe_allow_html=True)
    st.markdown("### Evidence to retain")
    for i, item in enumerate(evidence):
        st.checkbox(item, key=f"real_guide_{bid}_{i}")
    st.markdown("### Do not close until")
    for item in do_not:
        st.warning(item)

    st.markdown("### Choose the resolution method")
    st.caption("This choice records intent. It does not close the break. Every path still requires action and verification.")
    a, b, c = st.columns(3)
    if a.button("Resolve Manually →", type="primary", use_container_width=True, key="guide_manual_real"):
        st.session_state["resolution_choice"] = "Manual"
        bb.audit("MANUAL_RESOLUTION_CHOICE_VIEWED", bid, "Analyst chose the manual resolution path from the guide")
        go("Resolution Control")
    if b.button("Assisted Resolution →", use_container_width=True, key="guide_assisted_real"):
        st.session_state["resolution_choice"] = "Assisted"
        bb.audit("ASSISTED_RESOLUTION_CHOICE_VIEWED", bid, "Analyst chose the controlled assisted resolution path from the guide")
        go("Resolution Control")
    if c.button("Escalate →", use_container_width=True, key="guide_escalate_real"):
        st.session_state["resolution_choice"] = "Escalate"
        bb.audit("ESCALATION_CHOICE_VIEWED", bid, "Analyst chose escalation after reviewing the guide")
        go("Resolution Control")


def render_resolution():
    css()
    bid = st.session_state.get("selected_break")
    if not bid:
        st.info("Choose a break first.")
        return
    case = bb.get_case(bid)
    if not case:
        st.warning("Complete the case review first.")
        return
    operator = st.session_state.get("operator_id", "OPS-1047")
    status = case.get("status")
    choice = st.session_state.get("resolution_choice")
    st.markdown(f'<div class="rc-title">Resolution · {bid}</div>', unsafe_allow_html=True)
    st.markdown('<div class="rc-sub">Human action is recorded here. Closure is a separate verification step.</div>', unsafe_allow_html=True)

    if status in {"CASE_CREATED", "IN_REVIEW", "AWAITING_APPROVAL"}:
        if choice == "Escalate":
            st.markdown('<div class="rc-next"><div class="rc-label">Escalation</div><div class="rc-big">Keep the break open</div><div class="rc-muted">Escalation transfers ownership. It is not a closure action.</div></div>', unsafe_allow_html=True)
            notes = st.text_area("Why are you escalating?", key="esc_notes")
            if st.button("Record escalation →", type="primary", use_container_width=True, key="record_escalation"):
                bb.mark(bid, "ESCALATED", operator, notes or "Analyst escalated after reviewing the guide.")
                st.rerun()
            return
        if choice == "Assisted":
            st.markdown('<div class="rc-card"><div class="rc-label">Controlled assisted resolution</div><h3>Approval is required before the controlled action runs.</h3><div class="rc-muted">Review the proposal and evidence. This is the only path here that can invoke the controlled execution workflow.</div></div>', unsafe_allow_html=True)
            notes = st.text_area("Approval note", key="assist_notes")
            if st.button("Approve controlled action →", type="primary", use_container_width=True, key="assist_approve"):
                bb.approve(bid, operator, notes, mode="Assisted")
                st.rerun()
            return
        st.markdown('<div class="rc-card"><div class="rc-label">Ready to choose</div><h3>How will you resolve this break?</h3><div class="rc-muted">If you have not read the Resolution Guide, go back first. Manual resolution does not execute anything inside Resolvia and does not close the break.</div></div>', unsafe_allow_html=True)
        if st.button("Open Resolution Guide →", type="primary", use_container_width=True, key="back_guide"):
            go("Resolution Playbook")
        return

    if status == "MANUAL_IN_PROGRESS":
        st.markdown('<div class="rc-next"><div class="rc-label">Manual correction</div><div class="rc-big">Record what you actually did</div><div class="rc-muted">Perform the correction in the relevant operational system. Resolvia is recording the human action; it is not pretending to execute the manual correction.</div></div>', unsafe_allow_html=True)
        action = st.text_area("Action performed", placeholder="Example: Updated the SSI after confirmation from Settlements Operations.", key="manual_action_real")
        reference = st.text_input("Confirmation / evidence reference", placeholder="Ticket, confirmation ID, SSI reference, reconciliation reference…", key="manual_reference_real")
        checks = [st.checkbox(x, key=f"manual_real_check_{i}") for i, x in enumerate([
            "I verified the correct record before making the correction.",
            "The owning department confirmed the correction where required.",
            "I have retained the supporting evidence/reference.",
        ])]
        if st.button("Submit manual action for verification →", type="primary", use_container_width=True, key="manual_submit_real"):
            try:
                bb.submit_manual(bid, operator, action, reference, checks)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return

    if status == "AWAITING_VERIFICATION":
        st.markdown('<div class="rc-next"><div class="rc-label">Independent verification</div><div class="rc-big">Verify before closure</div><div class="rc-muted">Check the correction against the relevant source record. The verifier records what was checked.</div></div>', unsafe_allow_html=True)
        verifier = st.text_input("Verifier Operations ID", value=operator, key="real_verifier")
        notes = st.text_area("Verification notes", placeholder="What did you check and what confirms the break is resolved?", key="real_verification_notes")
        if st.button("Verify & close case →", type="primary", use_container_width=True, key="real_verify_close"):
            try:
                bb.verify_manual(bid, verifier, notes)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return

    if status == "CLOSED":
        st.success("This case is closed after verification.")
    elif status == "ESCALATED":
        st.warning("This case is escalated and remains open.")
    if st.button("View this break's audit →", key="real_resolution_audit"):
        audit(bid)
