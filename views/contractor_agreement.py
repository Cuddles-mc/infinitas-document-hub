"""Contractor Agreement page — sole trader and limited company."""

import streamlit as st
from datetime import date
from ui import page_header, step_flow, form_section, draft_resume_block, convert_docx_to_pdf


def render(user_email: str):
    page_header("Contractor Agreement", "Sole trader or limited company contractor agreements")

    has_generated = "ca_generated" in st.session_state
    current_step = 1 if has_generated else 0
    step_flow(["Fill Details", "Download"], current_step)

    if has_generated:
        _render_download()
        return

    # Draft resume
    if draft_resume_block(user_email, "contractor_agreement", _restore_draft):
        st.stop()

    _render_form(user_email)


def _restore_draft(fd: dict):
    ctype = fd.get("type", "sole_trader")
    st.session_state["ca_type"] = "Limited Company" if ctype == "ltd_company" else "Sole Trader"
    st.session_state["ca_nominated_client"] = fd.get("nominated_client", "")
    st.session_state["ca_role"] = fd.get("role", "")
    for dk in ("commencement_date", "end_date"):
        if fd.get(dk):
            try:
                st.session_state[f"ca_{dk}"] = date.fromisoformat(fd[dk])
            except ValueError:
                pass
    st.session_state["ca_hours_of_work"] = fd.get("hours_of_work", "")
    st.session_state["ca_contract_rate"] = fd.get("contract_rate", "")
    st.session_state["ca_notice_period"] = fd.get("notice_period", "")
    st.session_state["ca_travel_expenses"] = fd.get(
        "travel_expenses", "Upon authorisation by the Nominated Client",
    )
    if ctype == "ltd_company":
        st.session_state["ca_provider_company"] = fd.get("provider_company", "")
        st.session_state["ca_trading_as"] = fd.get("trading_as", "")
        st.session_state["ca_registered_address"] = fd.get("registered_address", "")
        st.session_state["ca_company_nzbn"] = fd.get("company_nzbn", "")
        st.session_state["ca_individual_contractor"] = fd.get("individual_contractor", "")
        st.session_state["ca_ird_number"] = fd.get("ird_number", "")
        st.session_state["ca_gst_registered"] = fd.get("gst_registered", "No")
        st.session_state["ca_gst_number"] = fd.get("gst_number", "")
        st.session_state["ca_bank_account"] = fd.get("bank_account", "")


def _render_form(user_email: str):
    from generators.contractor_agreement import generate_docx as generate_ca
    from drafts import save_draft, delete_draft

    ca_type = st.radio(
        "Contractor type",
        ["Sole Trader", "Limited Company"],
        key="ca_type",
        horizontal=True,
    )
    is_ltd = ca_type == "Limited Company"

    # Ltd Company extra fields
    if is_ltd:
        form_section("Company Details")
        l1, l2 = st.columns(2)
        with l1:
            st.text_input("Provider company name *", key="ca_provider_company")
            st.text_input("Trading as (if applicable)", key="ca_trading_as")
            st.text_input("Company No. / NZBN", key="ca_company_nzbn")
        with l2:
            st.text_area("Registered address", height=80, key="ca_registered_address")
            st.text_input("Name of Individual Contractor *", key="ca_individual_contractor")
            st.text_input("IRD Number", key="ca_ird_number")

        g1, g2 = st.columns(2)
        with g1:
            ca_gst = st.radio("GST Registered", ["No", "Yes"], key="ca_gst_registered", horizontal=True)
        with g2:
            if ca_gst == "Yes":
                st.text_input("GST Number", key="ca_gst_number")
        st.text_input("Nominated Bank Account Number", key="ca_bank_account")

    # Assignment details
    form_section("Assignment Details")
    c1, c2 = st.columns(2)
    with c1:
        ca_client = st.text_input("Nominated Client *", key="ca_nominated_client")
        st.text_input("Role *", key="ca_role")
        st.date_input("Commencement Date", key="ca_commencement_date")
        st.text_input("Hours of Work", key="ca_hours_of_work")
    with c2:
        st.text_input("Contract Rate *", key="ca_contract_rate")
        st.date_input("End Date", key="ca_end_date")
        st.text_input("Notice Period", key="ca_notice_period")
        st.text_input(
            "Other/Travel Expenses",
            value="Upon authorisation by the Nominated Client",
            key="ca_travel_expenses",
        )

    form_section("Output")
    fmt1, fmt2 = st.columns(2)
    with fmt1:
        st.markdown("**Format**")
        ca_fmt_docx = st.checkbox(".docx", value=True, key="ca_fmt_docx")
        ca_fmt_pdf = st.checkbox(".pdf", key="ca_fmt_pdf")
    with fmt2:
        st.markdown("**E-Signature**")
        ca_docusign = st.checkbox(
            "Add DocuSign fields",
            key="ca_docusign",
            help="Embeds invisible text tags so DocuSign can auto-detect signature, name, and date fields.",
        )

    # Auto-save draft
    if ca_client and "ca_generated" not in st.session_state:
        _save_draft(user_email, ca_client, is_ltd)

    # Generate
    st.markdown("")
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        generate = st.button("Generate Agreement", type="primary", key="ca_generate", use_container_width=True)

    if generate:
        missing = []
        if not ca_client:
            missing.append("Nominated Client")
        if not st.session_state.get("ca_role"):
            missing.append("Role")
        if not st.session_state.get("ca_contract_rate"):
            missing.append("Contract Rate")
        if is_ltd and not st.session_state.get("ca_provider_company"):
            missing.append("Provider company name")
        if is_ltd and not st.session_state.get("ca_individual_contractor"):
            missing.append("Individual Contractor name")
        if not ca_fmt_docx and not ca_fmt_pdf:
            missing.append("At least one output format")

        if missing:
            st.error(f"Please fill in: {', '.join(missing)}")
        else:
            com_date = st.session_state.get("ca_commencement_date", date.today())
            end_date = st.session_state.get("ca_end_date", date.today())
            gen_data = {
                "contractor_type": "ltd_company" if is_ltd else "sole_trader",
                "date_of_agreement": f"{date.today().day} {date.today().strftime('%B')} {date.today().year}",
                "nominated_client": ca_client,
                "role": st.session_state.get("ca_role", ""),
                "commencement_date": f"{com_date.day} {com_date.strftime('%B')} {com_date.year}",
                "end_date": f"{end_date.day} {end_date.strftime('%B')} {end_date.year}",
                "hours_of_work": st.session_state.get("ca_hours_of_work", ""),
                "contract_rate": st.session_state.get("ca_contract_rate", ""),
                "notice_period": st.session_state.get("ca_notice_period", ""),
                "travel_expenses": st.session_state.get(
                    "ca_travel_expenses", "Upon authorisation by the Nominated Client",
                ),
                "docusign": st.session_state.get("ca_docusign", False),
            }
            if is_ltd:
                gen_data.update({
                    "provider_company": st.session_state.get("ca_provider_company", ""),
                    "trading_as": st.session_state.get("ca_trading_as", ""),
                    "registered_address": st.session_state.get("ca_registered_address", ""),
                    "company_nzbn": st.session_state.get("ca_company_nzbn", ""),
                    "individual_contractor": st.session_state.get("ca_individual_contractor", ""),
                    "ird_number": st.session_state.get("ca_ird_number", ""),
                    "gst_registered": st.session_state.get("ca_gst_registered", "No") == "Yes",
                    "gst_number": st.session_state.get("ca_gst_number", ""),
                    "bank_account": st.session_state.get("ca_bank_account", ""),
                })
            try:
                docx_bytes = generate_ca(gen_data)
                st.session_state["ca_generated"] = docx_bytes
                st.session_state["ca_gen_data"] = gen_data
                st.session_state["ca_fmt_docx"] = ca_fmt_docx
                st.session_state["ca_fmt_pdf"] = ca_fmt_pdf
                delete_draft(user_email, "contractor_agreement")
                st.rerun()
            except Exception as e:
                st.error(f"Error generating document: {e}")


def _render_download():
    gen_data = st.session_state["ca_gen_data"]
    docx_bytes = st.session_state["ca_generated"]
    ca_fmt_docx = st.session_state.get("ca_fmt_docx", True)
    ca_fmt_pdf = st.session_state.get("ca_fmt_pdf", False)
    ctype_label = "Sole Trader" if gen_data["contractor_type"] == "sole_trader" else "Ltd Company"
    fname_base = f"Contractor Agreement - {ctype_label} - {gen_data['nominated_client']}"

    # Back button
    if st.button("< Back to form"):
        del st.session_state["ca_generated"]
        del st.session_state["ca_gen_data"]
        st.rerun()

    form_section("Download")

    if ca_fmt_docx:
        st.download_button(
            f"Download {fname_base}.docx",
            docx_bytes, f"{fname_base}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            key="ca_dl_docx",
        )
    if ca_fmt_pdf:
        pdf = convert_docx_to_pdf(docx_bytes)
        if pdf:
            st.download_button(
                f"Download {fname_base}.pdf",
                pdf, f"{fname_base}.pdf",
                mime="application/pdf",
                key="ca_dl_pdf",
            )
        else:
            st.warning("PDF conversion failed.")


def _save_draft(user_email: str, ca_client: str, is_ltd: bool):
    from drafts import save_draft
    draft_data = {
        "type": "ltd_company" if is_ltd else "sole_trader",
        "nominated_client": ca_client,
        "role": st.session_state.get("ca_role", ""),
        "commencement_date": str(st.session_state.get("ca_commencement_date", "")),
        "end_date": str(st.session_state.get("ca_end_date", "")),
        "hours_of_work": st.session_state.get("ca_hours_of_work", ""),
        "contract_rate": st.session_state.get("ca_contract_rate", ""),
        "notice_period": st.session_state.get("ca_notice_period", ""),
        "travel_expenses": st.session_state.get(
            "ca_travel_expenses", "Upon authorisation by the Nominated Client",
        ),
    }
    if is_ltd:
        draft_data.update({
            "provider_company": st.session_state.get("ca_provider_company", ""),
            "trading_as": st.session_state.get("ca_trading_as", ""),
            "registered_address": st.session_state.get("ca_registered_address", ""),
            "company_nzbn": st.session_state.get("ca_company_nzbn", ""),
            "individual_contractor": st.session_state.get("ca_individual_contractor", ""),
            "ird_number": st.session_state.get("ca_ird_number", ""),
            "gst_registered": st.session_state.get("ca_gst_registered", "No"),
            "gst_number": st.session_state.get("ca_gst_number", ""),
            "bank_account": st.session_state.get("ca_bank_account", ""),
        })
    save_draft(user_email, "contractor_agreement", draft_data)
