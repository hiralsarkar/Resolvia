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

    # Supplemental documents are scoped to this break and saved in the case
    # store, so they survive reloads; they never overwrite the original RCA.
    st.markdown("### Additional evidence")
    st.caption("Upload new documents for this break. RESOLVIA extracts their contents and creates a separate supplemental review; the original analysis and approval controls remain unchanged.")
    import document_evidence as de
    uploaded = st.file_uploader(
        "Upload supporting files for this break",
        type=["pdf", "docx", "txt", "csv", "xlsx", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key=f"supplemental_uploader_{bid}",
        help="Maximum 8 MB per file. Scanned PDFs are not supported yet; use a text PDF or upload the extracted text."
    )
    if st.button("Process uploaded documents", key=f"process_supplemental_{bid}", use_container_width=True):
        existing_hashes = {d["sha256"] for d in bb.supplemental_documents(bid)}
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
                    "uploaded_at": bb.now_iso(),
                }
                bb.add_supplemental_document(bid, record)
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

    documents = bb.supplemental_documents(bid)
    reviews = bb.supplemental_reviews(bid)
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
                    review["version"] = len(reviews) + 1
                    bb.add_supplemental_review(bid, review)
                    bb.audit("SUPPLEMENTAL_EVIDENCE_REVIEWED", bid,
                             f"Supplemental review version {review['version']} using {len(documents)} document(s)",
                             metadata={"version": review["version"], "mode": review["mode"],
                                       "document_count": len(documents)})
                    st.rerun()
                except Exception as exc:
                    st.error(f"Supplemental review failed: {exc}")
        for review in reviews:
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

    if status in bb.DECISION_STATUSES:
        if status == "ESCALATED":
            st.warning("Escalated. The break stays open until the receiving owner approves a fix, resolves it manually or hands it back.")
        st.markdown('<div class="rc-next"><div class="rc-label">Next step</div><div class="rc-big">Read the Resolution Guide</div><div class="rc-muted">Before choosing a resolution method, review who owns the correction, what must be checked, which evidence is required, and when to escalate.</div></div>', unsafe_allow_html=True)
        if st.button("Read Resolution Guide →", type="primary", use_container_width=True, key="real_read_guide"):
            bb.audit("RESOLUTION_GUIDE_OPENED", bid, "Analyst opened the manual resolution guide")
            go("Resolution Playbook")
    elif status == "REOPENED":
        st.markdown('<div class="rc-next"><div class="rc-label">Reopened</div><div class="rc-big">The fix did not hold</div><div class="rc-muted">Validation found the records still disagree after the automated fix. Resolve it manually (with independent verification) or escalate it.</div></div>', unsafe_allow_html=True)
        if st.button("Choose how to resolve →", type="primary", use_container_width=True, key="real_reopened"):
            go("Resolution Control")
    elif status == "MANUAL_IN_PROGRESS":
        st.markdown('<div class="rc-next"><div class="rc-label">Manual action in progress</div><div class="rc-big">Break remains OPEN</div><div class="rc-muted">The analyst selected manual resolution. Perform the correction in the appropriate operational system, then return to record exactly what was done.</div></div>', unsafe_allow_html=True)
        if st.button("Record manual action →", type="primary", use_container_width=True, key="real_record_manual"):
            go("Resolution Control")
    elif status == "AWAITING_VERIFICATION":
        st.markdown('<div class="rc-next"><div class="rc-label">Awaiting verification</div><div class="rc-big">Do not close yet</div><div class="rc-muted">The manual action is recorded. A different person must verify it before closure.</div></div>', unsafe_allow_html=True)
        if st.button("Verify manual resolution →", type="primary", use_container_width=True, key="real_verify"):
            go("Resolution Control")
    elif status == "CLOSED":
        resolution_card(case)
    elif status == "REJECTED":
        st.error("The proposed fix was rejected. Nothing was changed.")

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
        st.session_state[f"resolution_choice::{bid}"] = "Manual"
        bb.audit("MANUAL_RESOLUTION_CHOICE_VIEWED", bid, "Analyst chose the manual resolution path from the guide")
        go("Resolution Control")
    if b.button("Assisted Resolution →", use_container_width=True, key="guide_assisted_real"):
        st.session_state[f"resolution_choice::{bid}"] = "Assisted"
        bb.audit("ASSISTED_RESOLUTION_CHOICE_VIEWED", bid, "Analyst chose the controlled assisted resolution path from the guide")
        go("Resolution Control")
    if c.button("Escalate →", use_container_width=True, key="guide_escalate_real"):
        st.session_state[f"resolution_choice::{bid}"] = "Escalate"
        bb.audit("ESCALATION_CHOICE_VIEWED", bid, "Analyst chose escalation after reviewing the guide")
        go("Resolution Control")


def resolution_card(case):
    rec = bb.resolution_record(case)
    if not rec:
        return
    when = pd.to_datetime(rec["closed_at"], utc=True).strftime("%d %b %Y · %H:%M UTC") if rec["closed_at"] else "-"
    ref = f'<br><b>Evidence reference:</b> {rec["evidence_reference"]}' if rec.get("evidence_reference") else ""
    st.markdown(f'<div class="rc-card" style="border-color:#1f6f55"><div class="rc-label" style="color:#34E5A6">Resolved &amp; verified</div>'
                f'<h3>{rec["how"]}</h3><div class="rc-muted"><b>Closed:</b> {when}<br><b>By:</b> {rec["by"]}<br>'
                f'<b>Verification:</b> {rec.get("validation") or "-"}{ref}</div></div>', unsafe_allow_html=True)


def _choice_buttons(bid, allowed):
    cols = st.columns(len(allowed))
    labels = {"Manual": "Resolve manually", "Assisted": "Assisted (approve fix)", "Escalate": "Escalate"}
    for col, opt in zip(cols, allowed):
        if col.button(labels[opt], use_container_width=True, key=f"choose_{opt}_{bid}",
                      type="primary" if opt == allowed[0] else "secondary"):
            st.session_state[f"resolution_choice::{bid}"] = opt
            bb.audit(f"{opt.upper()}_RESOLUTION_CHOICE_VIEWED" if opt != "Escalate" else "ESCALATION_CHOICE_VIEWED",
                     bid, f"Analyst chose the {opt.lower()} path")
            st.rerun()


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
    proposal = case.get("proposal") or {}
    gate = case.get("gate_result") or {}
    choice_key = f"resolution_choice::{bid}"
    choice = st.session_state.get(choice_key)
    st.markdown(f'<div class="rc-title">Resolution · {bid}</div>', unsafe_allow_html=True)
    st.markdown('<div class="rc-sub">Human action is recorded here. Closure is a separate verification step. Everything you do is saved and stays after a reload.</div>', unsafe_allow_html=True)
    st.markdown(f"**Status:** {status_label(status)}")

    if status in bb.DECISION_STATUSES or status == "REOPENED":
        allowed = ["Manual", "Escalate"] if status == "REOPENED" else (
            ["Assisted", "Manual", "Escalate"] if not gate.get("authorized") else ["Manual", "Escalate"])
        if status == "ESCALATED":
            allowed = [a for a in allowed if a != "Escalate"]
        if choice not in allowed:
            choice = None
        if proposal:
            st.markdown(f'<div class="rc-card"><div class="rc-label">Proposed resolution</div><h3>{proposal.get("recommended_action", "")}</h3><div class="rc-muted">{proposal.get("reason", "")}</div></div>', unsafe_allow_html=True)
        if status == "ESCALATED":
            st.warning("This break was escalated. As the receiving owner you can approve the controlled fix or resolve it manually.")
        if status == "REOPENED":
            st.warning("Validation reopened this break after the automated fix. Resolve it manually or escalate it.")

        if choice is None:
            st.markdown("### How will you resolve this break?")
            st.caption("Not sure? Read the Resolution Guide first.")
            _choice_buttons(bid, allowed)
            if st.button("Open Resolution Guide", use_container_width=True, key="back_guide"):
                go("Resolution Playbook")
            return

        if st.button("← Choose a different path", key=f"rechoose_{bid}"):
            st.session_state.pop(choice_key, None)
            st.rerun()

        if choice == "Escalate":
            st.markdown('<div class="rc-next"><div class="rc-label">Escalation</div><div class="rc-big">Keep the break open</div><div class="rc-muted">Escalation transfers ownership. It is not a closure action.</div></div>', unsafe_allow_html=True)
            notes = st.text_area("Why are you escalating?", key=f"esc_notes_{bid}")
            if st.button("Record escalation →", type="primary", use_container_width=True, key="record_escalation"):
                bb.mark(bid, "ESCALATED", operator, notes or "Analyst escalated after reviewing the guide.")
                st.session_state.pop(choice_key, None)
                st.rerun()
            return

        if choice == "Assisted":
            st.markdown('<div class="rc-card"><div class="rc-label">Controlled assisted resolution</div><h3>Approval is required before the controlled action runs.</h3><div class="rc-muted">Review the proposal and evidence. Approving runs the controlled fix and then re-checks the records; the case closes only if validation passes.</div></div>', unsafe_allow_html=True)
            notes = st.text_area("Approval note", placeholder="What did you verify before approving?", key=f"assist_notes_{bid}")
            a, b = st.columns(2)
            if a.button("Approve controlled action →", type="primary", use_container_width=True, key="assist_approve"):
                with st.status("Carrying out the fix and re-checking it", expanded=True) as s:
                    bb.approve(bid, operator, notes, mode="Assisted",
                               on_event=lambda stage, label, detail: st.write(f"{label}: {detail}"))
                    s.update(label="Done", state="complete")
                st.session_state.pop(choice_key, None)
                st.rerun()
            if b.button("Reject the proposal", use_container_width=True, key="assist_reject"):
                bb.reject(bid, operator, notes or "Rejected after review")
                st.session_state.pop(choice_key, None)
                st.rerun()
            return

        if choice == "Manual":
            st.markdown('<div class="rc-next"><div class="rc-label">Manual resolution</div><div class="rc-big">You will make the correction yourself</div><div class="rc-muted">Resolvia does not execute anything on this path. The break stays open while you correct it in the owning system, then you record what you did and a different person verifies it.</div></div>', unsafe_allow_html=True)
            notes = st.text_input("Note (optional)", placeholder="e.g. Correcting SSI in the settlement system", key=f"manual_start_note_{bid}")
            if st.button("Start manual resolution →", type="primary", use_container_width=True, key="manual_start"):
                try:
                    bb.begin_manual(bid, operator, notes)
                    st.session_state.pop(choice_key, None)
                    st.rerun()
                except Exception as exc:
                    st.error(str(exc))
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
        mr = case.get("manual_resolution") or {}
        st.markdown('<div class="rc-next"><div class="rc-label">Independent verification</div><div class="rc-big">Verify before closure</div><div class="rc-muted">A different person checks the correction against the source record and records what was checked (four-eyes).</div></div>', unsafe_allow_html=True)
        st.markdown(f"**Correction recorded by:** {mr.get('submitted_by', '-')}  \n**What was done:** {mr.get('action_taken', '-')}  \n**Reference:** {mr.get('evidence_reference', '-')}")
        verifier = st.text_input("Verifier Operations ID", value="" if operator == mr.get("submitted_by") else operator,
                                 placeholder="A different Operations ID, e.g. OPS-3051", key="real_verifier")
        notes = st.text_area("Verification notes", placeholder="What did you check and what confirms the break is resolved?", key="real_verification_notes")
        if st.button("Verify & close case →", type="primary", use_container_width=True, key="real_verify_close"):
            try:
                bb.verify_manual(bid, verifier, notes)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
        return

    if status == "CLOSED":
        resolution_card(case)
    elif status == "REJECTED":
        st.error("The proposed fix was rejected. Nothing was changed.")
    if st.button("View this break's audit →", key="real_resolution_audit"):
        audit(bid)
