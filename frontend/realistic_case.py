"""Case and resolution pages, built around the analyst.

The flow runs:
Review -> Understand -> Read Guide -> Choose method -> Act -> Verify -> Close.
Choosing Manual never closes a case and never counts as approval.
"""
import streamlit as st
import pandas as pd
from html import escape
import backend_bridge as bb
from theme import COLORS, STATUS_LABEL, SEVERITY_LABEL, page_header, root_cause_label


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
    .rc-sub{color:#C2C6D6;margin:.25rem 0 1.2rem}
    .rc-card{background:#12141d;border:1px solid #272d3b;border-radius:16px;padding:20px;margin:0 0 14px}
    .rc-next{background:#151b25;border:1px solid #3a4b60;border-radius:16px;padding:22px;margin:14px 0}
    .rc-label{font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;color:#C2C6D6;font-weight:800}
    .rc-big{font-size:1.8rem;font-weight:800}
    .rc-muted{color:#C2C6D6;font-size:.84rem}
    .rc-step{border-left:3px solid #354052;padding:5px 0 5px 14px;margin:9px 0}
    .rc-step strong{display:block}
    .flow-bar{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0 20px;padding:12px 14px;background:#12141d;border:1px solid #272d3b;border-radius:14px}
    .flow-step{font-size:.72rem;font-weight:800;display:flex;gap:6px;align-items:center}
    .flow-dot{border:1px solid currentColor;border-radius:50%;width:21px;height:21px;display:inline-flex;align-items:center;justify-content:center;font-size:.65rem}
    .flow-line{height:1px;background:#3a4050;flex:1;min-width:10px}
    .stApp .main, .stApp .main *{font-family:Inter,ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}
    .stApp .main h1,.stApp .main h2,.stApp .main h3,.stApp .main h4{font-family:Inter,ui-sans-serif,system-ui,sans-serif!important;letter-spacing:-.025em!important}
    .stApp .main [data-testid="stMetricValue"]{font-family:Inter,ui-sans-serif,system-ui,sans-serif!important;font-size:1.55rem!important;line-height:1.1!important;letter-spacing:-.03em!important;white-space:normal!important;overflow-wrap:anywhere!important}
    .stApp .main [data-testid="stMetricLabel"]{font-family:Inter,ui-sans-serif,system-ui,sans-serif!important;font-size:.78rem!important;font-weight:700!important;letter-spacing:.02em!important}
    .stApp .main .mono{font-family:"SFMono-Regular",Consolas,"Liberation Mono",monospace!important}
    .stApp .main .ph-title{font-family:Inter,ui-sans-serif,system-ui,sans-serif!important;font-size:2.45rem!important;letter-spacing:-.045em!important}
    .stApp .main .ph-sub{font-family:Inter,ui-sans-serif,system-ui,sans-serif!important}
    .stApp .main .rc-big{font-family:Inter,ui-sans-serif,system-ui,sans-serif!important;letter-spacing:-.035em!important}
    .stApp .main .block-container{max-width:1360px;padding-top:2rem;padding-bottom:4rem}
    .stApp .main [data-testid="stHorizontalBlock"]{gap:1rem}
    .stApp,.stAppViewContainer,[data-testid="stAppViewContainer"]{background:radial-gradient(900px 500px at 8% 0%,rgba(102,72,190,.32),transparent 62%),radial-gradient(800px 600px at 100% 70%,rgba(24,110,180,.22),transparent 65%),#080a12!important}
    .stApp .main .rc-card,.stApp .main .rc-next{background:linear-gradient(145deg,rgba(71,51,126,.26),rgba(16,18,30,.78))!important;border:1px solid rgba(184,164,255,.18)!important;border-radius:22px!important;box-shadow:0 18px 50px rgba(0,0,0,.18)!important;padding:24px 26px!important}
    .stApp .main .rc-card:hover,.stApp .main .rc-next:hover{transform:none!important;border-color:rgba(112,214,255,.55)!important}
    .case-stat{background:linear-gradient(145deg,rgba(75,55,137,.32),rgba(18,20,34,.78));border:1px solid rgba(185,170,255,.18);border-radius:18px;padding:16px 18px;min-height:82px}
    .case-stat-label{color:#B8B4CC;font-size:.76rem;font-weight:700;letter-spacing:.04em}
    .case-stat-value{color:#F7F5FF;font-size:1.7rem;font-weight:750;line-height:1.15;margin-top:8px;letter-spacing:-.035em;overflow-wrap:anywhere}
    .case-stat-value.mono{font-family:Inter,ui-sans-serif,system-ui,sans-serif!important}
    .stApp .main .rc-label{color:#77DDF5!important;letter-spacing:.14em!important}
    div[data-testid="stButton"]>button{min-height:45px;border-radius:10px;font-weight:750}
    </style>""", unsafe_allow_html=True)


def case_audit(bid):
    events = bb.audit_events(break_id=bid, limit=100)
    if not events:
        st.caption("No activity recorded yet.")
        return
    rows = []
    for e in events:
        actor = e.get("actor_id", "SYSTEM")
        rows.append({
            "Time": pd.to_datetime(e["timestamp"], utc=True).strftime("%d %b %Y · %H:%M UTC"),
            "Type": "Human" if actor != "SYSTEM" else "System",
            "Operations ID": actor,
            "Action": e.get("action", ""),
            "What was done": e.get("detail", ""),
        })
    audit_df = pd.DataFrame(rows)
    st.dataframe(audit_df, hide_index=True, width="stretch", height=300)
    st.download_button("Download case audit", audit_df.to_csv(index=False).encode("utf-8"), f"{bid}-audit.csv", "text/csv", key=f"case_audit_download_{bid}")


_POINTS = {"MAND": "Mandatory", "VOLU": "Voluntary (election needed)"}
_VERDICT = {
    "agreed": "All readable signals agree, so the notice decided this case.",
    "conflict": "The signals disagree, so the notice was not used. A person decides.",
    "unreadable": "No signal could be read from the notice. A person decides.",
}

_FLOW = ["Review", "Understand", "Guide", "Choose", "Act", "Verify", "Audit"]

def _flow_step(status, case):
    if not case:
        return 0
    if status in {"CLOSED", "REOPENED"}:
        return 6
    if status == "AWAITING_VERIFICATION":
        return 5
    if status == "MANUAL_IN_PROGRESS":
        return 4
    if case.get("proposal"):
        return 3
    if case.get("rca"):
        return 2
    return 1

def _render_flow(status, case):
    current = _flow_step(status, case)
    cells = []
    for i, label in enumerate(_FLOW):
        colour = "#34E5A6" if i < current else ("#4CE0FF" if i == current else "#9CA2B8")
        cells.append(f'<span class="flow-step" style="color:{colour}"><span class="flow-dot">{i + 1}</span>{label}</span>')
    st.markdown('<div class="flow-bar">' + '<span class="flow-line"></span>'.join(cells) + '</div>', unsafe_allow_html=True)


def _render_notice_signals(rca, investigation):
    """Which fields on the corporate action notice drove the decision."""
    doc = investigation.get("document_evidence") or {}
    is_ca = (investigation.get("corporate_action_context") or {}).get("is_corporate_action")
    if not is_ca:
        return
    signals = rca.get("notice_signals")
    reread_now = signals is None
    if reread_now:  # cases analysed before signals were recorded
        import rca as rca_agent
        signals = rca_agent.notice_signals(doc.get("text"))
    verdict = rca.get("notice_verdict") or ("unreadable" if not signals else
              ("agreed" if len({s["points_to"] for s in signals}) == 1 else "conflict"))
    finding = rca.get("document_finding") or {}
    note = _VERDICT[verdict]
    if verdict == "agreed" and finding.get("changed"):
        note += f" It overrode the model's first read ({root_cause_label(finding['model_said'])})."
    rows = "".join(
        f'<tr><td>{escape(s["signal"].capitalize())}</td><td class="mono">{escape(s["field"])}</td>'
        f'<td class="mono">{escape(s["read"])}</td><td>{escape(_POINTS.get(s["points_to"], "Unknown"))}</td></tr>' for s in signals)
    table = (f'<table style="width:100%;margin-top:10px;border-collapse:collapse;font-size:0.9rem">'
             f'<tr style="text-align:left;opacity:.7"><th>Signal</th><th>Field</th><th>Value read</th><th>Points to</th></tr>{rows}</table>'
             if rows else "")
    src = f' Source: {escape(doc["doc_id"])}.' if doc.get("doc_id") else ""
    if reread_now:
        note = "Re-read now: this notice was not captured in the original decision record. " + note
    st.markdown(f'<div class="rc-card"><div class="rc-label">What drove the decision</div>'
                f'<div class="rc-muted">{escape(note)}{src}</div>{table}</div>', unsafe_allow_html=True)


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
    page_header("case", "Case Workspace", bid, f"{bb.issue_label(row)} · {row.counterparty}", COLORS["violet"])

    c1, c2, c3, c4 = st.columns(4)
    stats = [("Priority", SEVERITY_LABEL.get(row.severity, row.severity)),
             ("Exposure", f"₹{row.exposure:,.0f}"),
             ("Status", status_label(case.get("status", "NOT_STARTED")) if case else "Not started"),
             ("Operations ID", st.session_state.get("operator_id", "OPS-1047"))]
    for col, (label, value) in zip((c1, c2, c3, c4), stats):
        col.markdown(f'<div class="case-stat"><div class="case-stat-label">{escape(label)}</div><div class="case-stat-value">{escape(str(value))}</div></div>', unsafe_allow_html=True)

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

    _render_flow(status, case)

    reported = investigation.get("reported") or {}
    field = str(rca.get("field") or reported.get("field") or row.breaking_fields or "Not yet diagnosed")
    expected = str(rca.get("expected") or reported.get("expected") or "Not available")
    observed = str(rca.get("actual") or reported.get("actual") or "Not available")
    st.markdown(
        f'<div class="rc-card"><div class="rc-label">Responsible field</div>'
        f'<div class="rc-big mono">{escape(field)}</div>'
        f'<div class="rc-muted">Expected: {escape(expected)} &nbsp; · &nbsp; Observed: {escape(observed)}</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="rc-card"><div class="rc-label">What happened</div><h3>' + escape(root_cause_label(rca["root_cause"]) if rca.get("root_cause") else str(row.reported_issue)) + '</h3><div class="rc-muted">' + escape(str(rca.get("explanation", ""))) + '</div></div>', unsafe_allow_html=True)

    _render_notice_signals(rca, investigation)

    calculation = rca.get("entitlement_calculation")
    if calculation and calculation.get("status") == "CALCULATED":
        ratio = calculation["ratio"]
        st.markdown(
            f'<div class="rc-card"><div class="rc-label">Calculation used</div>'
            f'<div class="rc-muted">Ratio definition: {escape(ratio["held"])} held → {escape(ratio["new"])} new '
            f'(multiplier {escape(ratio["resulting_multiplier"])}).</div>'
            f'<div class="mono">{escape(calculation["source_quantity"])} × {escape(ratio["resulting_multiplier"])} = '
            f'{escape(calculation["expected_quantity"])} vs custodian {escape(calculation["observed_quantity"])}; '
            f'delta {escape(calculation["delta"])}.</div></div>', unsafe_allow_html=True)

    with st.expander("See evidence used for the analysis", expanded=False):
        st.json(investigation.get("structured_evidence", {}))
        if investigation.get("document_evidence", {}).get("has_document"):
            st.write(investigation["document_evidence"].get("text", ""))

    # extra documents belong to this break only, live in the session, and
    # never overwrite the original RCA
    st.markdown("### Optional supporting documents")
    st.caption("Use this only when the original evidence needs context. Supplemental documents never replace the recorded analysis or approval controls.")
    import document_evidence as de
    evidence_key = f"supplemental_docs::{bid}"
    reviews_key = f"supplemental_reviews::{bid}"
    if evidence_key not in st.session_state:
        st.session_state[evidence_key] = []
    if reviews_key not in st.session_state:
        st.session_state[reviews_key] = []
    uploaded = st.file_uploader(
        "Upload supporting files for this break",
        type=["pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"supplemental_uploader_{bid}",
        help="Maximum 8 MB per file. Scanned PDFs are not supported yet; use a text PDF or upload the extracted text."
    )
    if st.button("Process uploaded documents", key=f"process_supplemental_{bid}", use_container_width=True):
        existing_hashes = {d["sha256"] for d in st.session_state[evidence_key]}
        added, errors = 0, []
        for file in uploaded or []:
            try:
                parsed = de.extract_text(file.name, file.getvalue())
                if parsed["sha256"] in existing_hashes:
                    continue
                record = {
                    "name": file.name, "text": parsed["text"], "method": parsed["method"],
                    "sha256": parsed["sha256"], "bytes": parsed["bytes"],
                    "truncated": parsed["truncated"],
                    "uploaded_by": st.session_state.get("operator_id", "OPS-1047"),
                    "uploaded_at": pd.Timestamp.utcnow().isoformat(),
                }
                st.session_state[evidence_key].append(record)
                existing_hashes.add(parsed["sha256"])
                added += 1
                bb.audit("SUPPLEMENTAL_DOCUMENT_PROCESSED", bid,
                         f"{file.name}; method={parsed['method']}; sha256={parsed['sha256']}",
                         actor_id=record["uploaded_by"],
                         metadata={"filename": file.name, "sha256": parsed["sha256"], "bytes": parsed["bytes"]})
            except Exception as exc:
                errors.append(f"{file.name}: {exc}")
        if added:
            bb.audit("SUPPLEMENTAL_EVIDENCE_ADDED", bid, f"{added} new document(s) attached to this case")
            st.success(f"Processed {added} new document(s).")
        elif not errors:
            st.info("No new documents were processed. Files may already be attached to this case.")
        for error in errors:
            st.error(error)
        st.rerun()

    documents = st.session_state[evidence_key]
    if documents:
        st.markdown(f"**Documents attached to this case: {len(documents)}**")
        for index, doc in enumerate(documents):
            with st.expander(f"{doc['name']} · {doc['method']}", expanded=False):
                st.caption(f"Uploaded by {doc['uploaded_by']} · {doc['uploaded_at']} · {doc['bytes']:,} bytes")
                st.caption(f"SHA-256: {doc['sha256']}")
                if doc["truncated"]:
                    st.warning("Extracted text was truncated to the first 30,000 characters.")
                st.text_area("Extracted text", value=doc["text"], height=180,
                             key=f"supplemental_text_{bid}_{index}", disabled=True)
        if st.button("Analyse with additional evidence →", type="primary",
                     key=f"analyse_supplemental_{bid}", use_container_width=True):
            with st.spinner("Reviewing supplemental evidence…"):
                try:
                    review = de.review_supplemental_evidence(bid, row, case, documents)
                    review["version"] = len(st.session_state[reviews_key]) + 1
                    st.session_state[reviews_key].append(review)
                    bb.audit("SUPPLEMENTAL_EVIDENCE_REVIEWED", bid,
                             f"Supplemental review version {review['version']} using {len(documents)} document(s)",
                             metadata={"version": review["version"], "mode": review["mode"],
                                       "document_count": len(documents)})
                    st.rerun()
                except Exception as exc:
                    st.error(f"Supplemental review failed: {exc}")
        for review in st.session_state[reviews_key]:
            with st.expander(f"Supplemental review v{review['version']} · {review['mode']}", expanded=True):
                st.caption(f"Created: {review['created_at']}")
                st.write(review["review"])
                if review.get("exact_matches"):
                    st.markdown("**Exact matches against selected case values**")
                    st.json(review["exact_matches"])
                st.info("This supplemental review does not overwrite the original root-cause model output, resolution proposal, or approval state. Treat extracted information as unverified until confirmed against an authoritative source.")
    else:
        st.caption("No additional documents attached to this case yet.")

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
    elif status == "ON_HOLD":
        st.info("On hold. This is a voluntary corporate action, so the position stays as it is until the client's election is received and logged.")
    elif status == "REOPENED":
        st.error("The fix did not clear the break when the records were checked again. It needs another look, not a retry.")

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
    root = (case.get("rca") or {}).get("root_cause")
    views = __import__("operational_views")
    playbooks = getattr(views, "PLAYBOOKS", {})
    default = getattr(views, "DEFAULT_PLAYBOOK")
    owner, escalation, reason, evidence, steps, do_not = playbooks.get(root, default)

    page_header("guide", "Manual Guide", f"Resolution Guide · {bid}", "Understand the correction first. Choose how to perform it only after reading this guide.", COLORS["accent"])
    st.markdown(f'<div class="rc-card"><div class="rc-label">Owner</div><h3>{owner}</h3><div class="rc-muted">Escalation: {escalation}</div><p>{reason}</p></div>', unsafe_allow_html=True)
    st.markdown("### Do this in order")
    for i, step in enumerate(steps, 1):
        st.markdown(f'<div class="rc-step"><strong>{i}. {step}</strong></div>', unsafe_allow_html=True)
    st.markdown("### Evidence to retain")
    checked = [st.checkbox(item, key=f"real_guide_{bid}_{i}") for i, item in enumerate(evidence)]
    st.markdown("### Do not close until")
    for item in do_not:
        st.warning(item)

    st.markdown("### Choose the resolution method")
    st.caption("This choice records intent. It does not close the break. Every path still requires action and verification.")
    a, b, c = st.columns(3)
    if not all(checked):
        st.caption("Complete the evidence checklist before choosing a resolution path.")
    if a.button("Resolve Manually →", type="primary", use_container_width=True, key="guide_manual_real", disabled=not all(checked)):
        st.session_state["resolution_choice"] = "Manual"
        bb.audit("MANUAL_RESOLUTION_CHOICE_VIEWED", bid, "Analyst chose the manual resolution path from the guide")
        go("Resolution Control")
    if b.button("Assisted Resolution →", use_container_width=True, key="guide_assisted_real", disabled=not all(checked)):
        st.session_state["resolution_choice"] = "Assisted"
        bb.audit("ASSISTED_RESOLUTION_CHOICE_VIEWED", bid, "Analyst chose the controlled assisted resolution path from the guide")
        go("Resolution Control")
    if c.button("Escalate →", use_container_width=True, key="guide_escalate_real", disabled=not all(checked)):
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
    page_header("resolution", "Resolution", f"Resolution · {bid}", "Human action is recorded here. Closure is a separate verification step.", COLORS["magenta"])

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
        verifier = st.text_input("Verifier Operations ID", value="", key="real_verifier", help="Must be a different, authorized verifier from the person who performed the action.")
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
        _render_notice_signals(case.get("rca") or {}, case.get("investigation") or {})
    elif status == "ESCALATED":
        st.warning("This case is escalated and remains open.")
    elif status == "ON_HOLD":
        st.info("On hold until the client's election is received.")
    elif status == "REOPENED":
        st.error("Verification failed: the break is still there after the fix.")
    if st.button("View this break's audit →", key="real_resolution_audit"):
        audit(bid)
