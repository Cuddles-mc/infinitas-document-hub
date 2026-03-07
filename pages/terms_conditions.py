"""Terms & Conditions page — toggleable clauses with live preview."""

import streamlit as st
from datetime import date
from ui import page_header, step_flow, form_section, draft_resume_block, convert_docx_to_pdf


# Clause descriptions for the live preview panel
CLAUSE_PREVIEWS = {
    "perm": {
        "title": "Permanent / Fixed Term Placement",
        "clauses": ["Placement Fee", "Liability to Pay a Placement Fee"],
        "description": "Covers permanent and fixed-term placements with fee calculations based on salary package.",
    },
    "contract": {
        "title": "Contractor / Temporary Worker",
        "clauses": ["Contractor or Temporary Worker Services", "Fees for Further Contracting"],
        "description": "Covers contractor and temporary worker arrangements with margin-based fees.",
    },
    "exec": {
        "title": "Retained / Executive Search",
        "clauses": ["Retained Assignment and Executive Search"],
        "description": "Covers senior/executive search with retained fee structure invoiced in thirds.",
    },
}


def render(user_email: str):
    page_header("Terms & Conditions", "Generate branded terms of business with toggleable clauses")

    has_generated = "tc_generated" in st.session_state
    current_step = 1 if has_generated else 0
    step_flow(["Configure", "Download"], current_step)

    if has_generated:
        _render_download()
        return

    # Draft resume
    if draft_resume_block(user_email, "terms_conditions", _restore_draft):
        st.stop()

    _render_form(user_email)


def _restore_draft(fd: dict):
    st.session_state["tc_client_name"] = fd.get("client_name", "")
    if fd.get("date"):
        try:
            st.session_state["tc_date"] = date.fromisoformat(fd["date"])
        except ValueError:
            pass
    st.session_state["tc_guarantee"] = fd.get("guarantee", 3)
    st.session_state["tc_perm_enabled"] = fd.get("perm_enabled", True)
    st.session_state["tc_contract_enabled"] = fd.get("contract_enabled", False)
    st.session_state["tc_exec_enabled"] = fd.get("exec_enabled", False)
    st.session_state["tc_perm_fee_pct"] = fd.get("perm_fee_pct", 18)
    st.session_state["tc_perm_basis"] = fd.get("perm_basis", "Total Salary Package")
    st.session_state["tc_perm_structure"] = fd.get("perm_structure", "Retained (thirds)")
    st.session_state["tc_perm_fixed_fee"] = fd.get("perm_fixed_fee", "")
    st.session_state["tc_contract_margin"] = fd.get("contract_margin", 25)
    st.session_state["tc_exec_fee_pct"] = fd.get("exec_fee_pct", 25)
    st.session_state["tc_exec_basis"] = fd.get("exec_basis", "Total Salary Package")
    st.session_state["tc_exec_structure"] = fd.get("exec_structure", "Retained (thirds)")
    st.session_state["tc_exec_fixed_fee"] = fd.get("exec_fixed_fee", "")
    st.session_state["tc_sig_infinitas"] = fd.get("sig_infinitas", False)
    st.session_state["tc_sig_client"] = fd.get("sig_client", False)


def _render_form(user_email: str):
    from generators.terms_conditions import generate_docx as generate_tc
    from drafts import save_draft, delete_draft

    form_section("Client")
    col1, col2 = st.columns(2)
    with col1:
        tc_client = st.text_input("Client company name *", key="tc_client_name")
        tc_date_val = st.date_input("Date", value=date.today(), key="tc_date")
    with col2:
        tc_guarantee = st.selectbox(
            "Guarantee period", [3, 6, 12],
            format_func=lambda x: f"{x} months", key="tc_guarantee",
        )

    # --- Service types with live clause preview ---
    form_section("Service Types")
    st.caption("Toggle which service types to include. The document will only contain relevant clauses.")

    svc1, svc2, svc3 = st.columns(3)
    with svc1:
        tc_perm = st.checkbox("Permanent / Fixed Term", value=True, key="tc_perm_enabled")
    with svc2:
        tc_contract = st.checkbox("Contractor / Temporary Worker", key="tc_contract_enabled")
    with svc3:
        tc_exec = st.checkbox("Retained / Executive Search", key="tc_exec_enabled")

    # Live clause preview — show what's included
    included = []
    if tc_perm:
        included.append(CLAUSE_PREVIEWS["perm"])
    if tc_contract:
        included.append(CLAUSE_PREVIEWS["contract"])
    if tc_exec:
        included.append(CLAUSE_PREVIEWS["exec"])

    if included:
        with st.expander("Clauses included in this document", expanded=False):
            for item in included:
                st.markdown(f"**{item['title']}**")
                st.caption(f"Clauses: {', '.join(item['clauses'])}")
                st.caption(item["description"])
                st.markdown("")
    else:
        st.warning("Please enable at least one service type.")

    # --- Fee details ---
    if tc_perm:
        form_section("Permanent / Fixed Term Fees")
        p1, p2, p3 = st.columns(3)
        with p1:
            st.number_input("Fee %", value=18, min_value=1, max_value=100, key="tc_perm_fee_pct")
        with p2:
            st.selectbox("Calculated on", ["Total Salary Package", "Base Salary"], key="tc_perm_basis")
        with p3:
            st.selectbox("Fee structure", ["Retained (thirds)", "Contingent", "Fixed Fee"], key="tc_perm_structure")
        if st.session_state.get("tc_perm_structure") == "Fixed Fee":
            st.text_input("Fixed fee amount", key="tc_perm_fixed_fee")

    if tc_contract:
        form_section("Contractor / Temporary Worker Fees")
        st.number_input("Margin %", value=25, min_value=1, max_value=100, key="tc_contract_margin")

    if tc_exec:
        form_section("Executive Search Fees")
        e1, e2, e3 = st.columns(3)
        with e1:
            st.number_input("Fee %", value=25, min_value=1, max_value=100, key="tc_exec_fee_pct")
        with e2:
            st.selectbox("Calculated on ", ["Total Salary Package", "Base Salary"], key="tc_exec_basis")
        with e3:
            st.selectbox("Fee structure ", ["Retained (thirds)", "Contingent", "Fixed Fee"], key="tc_exec_structure")
        if st.session_state.get("tc_exec_structure") == "Fixed Fee":
            st.text_input("Fixed fee amount ", key="tc_exec_fixed_fee")

    form_section("Signature Blocks")
    sig1, sig2 = st.columns(2)
    with sig1:
        st.checkbox("Include Infinitas signature", key="tc_sig_infinitas")
    with sig2:
        st.checkbox("Include Client signature", key="tc_sig_client")

    form_section("Output")
    fmt1, fmt2 = st.columns(2)
    with fmt1:
        tc_fmt_docx = st.checkbox(".docx", value=True, key="tc_fmt_docx")
        tc_fmt_pdf = st.checkbox(".pdf", key="tc_fmt_pdf")

    # Auto-save draft
    if tc_client and "tc_generated" not in st.session_state:
        _save_draft(user_email, tc_client)

    # Generate
    st.markdown("")
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        generate = st.button("Generate T&Cs", type="primary", key="tc_generate", use_container_width=True)

    if generate:
        if not tc_client:
            st.error("Please enter the client company name.")
        elif not tc_perm and not tc_contract and not tc_exec:
            st.error("Please enable at least one service type.")
        elif not tc_fmt_docx and not tc_fmt_pdf:
            st.error("Please select at least one output format.")
        else:
            structure_map = {
                "Retained (thirds)": "retained",
                "Contingent": "contingent",
                "Fixed Fee": "fixed_fee",
            }
            gen_data = {
                "client_name": tc_client,
                "date": str(st.session_state.get("tc_date", date.today())),
                "perm_enabled": st.session_state.get("tc_perm_enabled", True),
                "contract_enabled": st.session_state.get("tc_contract_enabled", False),
                "exec_enabled": st.session_state.get("tc_exec_enabled", False),
                "perm_fee_pct": st.session_state.get("tc_perm_fee_pct", 18),
                "perm_basis": st.session_state.get("tc_perm_basis", "Total Salary Package").lower(),
                "perm_structure": structure_map.get(
                    st.session_state.get("tc_perm_structure", "Retained (thirds)"), "retained",
                ),
                "perm_fixed_fee": st.session_state.get("tc_perm_fixed_fee", ""),
                "contract_margin_pct": st.session_state.get("tc_contract_margin", 25),
                "exec_fee_pct": st.session_state.get("tc_exec_fee_pct", 25),
                "exec_basis": st.session_state.get("tc_exec_basis", "Total Salary Package").lower(),
                "exec_structure": structure_map.get(
                    st.session_state.get("tc_exec_structure", "Retained (thirds)"), "retained",
                ),
                "exec_fixed_fee": st.session_state.get("tc_exec_fixed_fee", ""),
                "guarantee_months": st.session_state.get("tc_guarantee", 3),
                "sig_infinitas": st.session_state.get("tc_sig_infinitas", False),
                "sig_client": st.session_state.get("tc_sig_client", False),
                "adobe_sign": False,
            }
            try:
                docx_bytes = generate_tc(gen_data)
                st.session_state["tc_generated"] = docx_bytes
                st.session_state["tc_gen_data"] = gen_data
                st.session_state["tc_fmt_docx"] = tc_fmt_docx
                st.session_state["tc_fmt_pdf"] = tc_fmt_pdf
                delete_draft(user_email, "terms_conditions")
                st.rerun()
            except Exception as e:
                st.error(f"Error generating document: {e}")


def _render_download():
    gen_data = st.session_state["tc_gen_data"]
    docx_bytes = st.session_state["tc_generated"]
    tc_fmt_docx = st.session_state.get("tc_fmt_docx", True)
    tc_fmt_pdf = st.session_state.get("tc_fmt_pdf", False)
    fname_base = f"Infinitas Talent - Terms and Conditions - {gen_data['client_name']}"

    # Back button
    if st.button("< Back to form"):
        del st.session_state["tc_generated"]
        del st.session_state["tc_gen_data"]
        st.rerun()

    form_section("Download")

    if tc_fmt_docx:
        st.download_button(
            f"Download {fname_base}.docx",
            docx_bytes, f"{fname_base}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="tc_dl_docx",
        )
    if tc_fmt_pdf:
        pdf = convert_docx_to_pdf(docx_bytes)
        if pdf:
            st.download_button(
                f"Download {fname_base}.pdf",
                pdf, f"{fname_base}.pdf",
                mime="application/pdf",
                key="tc_dl_pdf",
            )
        else:
            st.warning("PDF conversion failed.")


def _save_draft(user_email: str, tc_client: str):
    from drafts import save_draft
    draft_data = {
        "client_name": tc_client,
        "date": str(st.session_state.get("tc_date", date.today())),
        "guarantee": st.session_state.get("tc_guarantee", 3),
        "perm_enabled": st.session_state.get("tc_perm_enabled", True),
        "contract_enabled": st.session_state.get("tc_contract_enabled", False),
        "exec_enabled": st.session_state.get("tc_exec_enabled", False),
        "perm_fee_pct": st.session_state.get("tc_perm_fee_pct", 18),
        "perm_basis": st.session_state.get("tc_perm_basis", "Total Salary Package"),
        "perm_structure": st.session_state.get("tc_perm_structure", "Retained (thirds)"),
        "perm_fixed_fee": st.session_state.get("tc_perm_fixed_fee", ""),
        "contract_margin": st.session_state.get("tc_contract_margin", 25),
        "exec_fee_pct": st.session_state.get("tc_exec_fee_pct", 25),
        "exec_basis": st.session_state.get("tc_exec_basis", "Total Salary Package"),
        "exec_structure": st.session_state.get("tc_exec_structure", "Retained (thirds)"),
        "exec_fixed_fee": st.session_state.get("tc_exec_fixed_fee", ""),
        "sig_infinitas": st.session_state.get("tc_sig_infinitas", False),
        "sig_client": st.session_state.get("tc_sig_client", False),
    }
    save_draft(user_email, "terms_conditions", draft_data)
