"""CV Preparation — standalone page for redacting CVs and adding cover pages."""

import streamlit as st
from ui import page_header, step_flow, form_section


def render():
    page_header("CV Preparation", "Upload CVs to redact personal details and add a branded cover page")

    has_pdfs = "cvp_pdfs" in st.session_state
    current_step = 1 if has_pdfs else 0
    step_flow(["Upload", "Download"], current_step)

    if has_pdfs:
        _render_download()
    else:
        _render_upload()


def _render_upload():
    form_section("Details")
    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client name *", key="cvp_client")
    with col2:
        st.text_input(
            "Candidate names (optional — auto-detected from CV)",
            key="cvp_names_hint",
            placeholder="Leave blank to auto-detect",
        )

    form_section("Upload CVs")
    uploaded = st.file_uploader(
        "Upload candidate CVs (PDF or DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="cvp_upload",
    )

    if uploaded:
        st.caption(f"{len(uploaded)} file(s) selected")

    st.markdown("")
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        go = st.button(
            "Generate redacted CVs",
            type="primary",
            use_container_width=True,
            disabled=not uploaded,
        )

    if go:
        if not client_name:
            st.error("Please enter the client name.")
            return
        if not uploaded:
            st.error("Please upload at least one CV.")
            return

        pdfs = {}
        progress = st.progress(0, text="Processing CVs...")

        for i, f in enumerate(uploaded):
            progress.progress(i / len(uploaded), text=f"Processing {f.name}...")

            try:
                cv_raw = f.read()

                # Try to detect candidate name from the CV text
                cand_name = _detect_name(cv_raw, f.name)
                if not cand_name:
                    cand_name = _name_from_filename(f.name)

                from generators.cv_pdf import generate_cv_pdf
                pdf_bytes = generate_cv_pdf(
                    candidate_name=cand_name,
                    client_name=client_name,
                    cv_file_bytes=cv_raw,
                    cv_filename=f.name,
                )
                pdf_name = f"CV of {cand_name} prepared for {client_name} by Infinitas.pdf"
                pdfs[pdf_name] = pdf_bytes

            except Exception as e:
                st.error(f"Error processing {f.name}: {e}")

        progress.progress(1.0, text="Done!")

        if pdfs:
            st.session_state.cvp_pdfs = pdfs
            st.session_state.cvp_client = client_name
            st.rerun()


def _render_download():
    if st.button("< Back"):
        del st.session_state["cvp_pdfs"]
        st.rerun()

    pdfs = st.session_state.cvp_pdfs
    client = st.session_state.cvp_client

    st.success(f"Generated {len(pdfs)} redacted CV(s) for **{client}**")

    form_section("Download")
    for name, data in pdfs.items():
        st.download_button(
            label=f"Download {name}",
            data=data,
            file_name=name,
            mime="application/pdf",
            key=f"cvp_dl_{name}",
        )

    st.caption("Personal details, links, and references have been removed. Cover page added.")

    # Zip if multiple
    if len(pdfs) > 1:
        import io, zipfile
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, fbytes in pdfs.items():
                zf.writestr(fname, fbytes)
        st.download_button(
            label="Download All (.zip)",
            data=zip_buf.getvalue(),
            file_name=f"CVs prepared for {client} by Infinitas.zip",
            mime="application/zip",
            type="primary",
            key="cvp_dl_zip",
        )

    st.divider()
    if st.button("Prepare more CVs"):
        for key in list(st.session_state.keys()):
            if key.startswith("cvp_"):
                del st.session_state[key]
        st.rerun()


def _detect_name(cv_bytes: bytes, filename: str) -> str:
    """Try to detect the candidate name from the CV using AI."""
    try:
        from views.shortlist import _extract_text_from_bytes
        text = _extract_text_from_bytes(cv_bytes, filename)
        if not text.strip():
            return ""

        from ai import extract_cv_data
        data = extract_cv_data(text)
        return data.get("name", "")
    except Exception:
        return ""


def _name_from_filename(filename: str) -> str:
    """Extract a candidate name from the filename as fallback."""
    import re
    name = filename.rsplit(".", 1)[0]
    # Strip common prefixes
    for prefix in ["CV of ", "CV - ", "CV_", "Resume of ", "Resume - ", "Resume_"]:
        if name.lower().startswith(prefix.lower()):
            name = name[len(prefix):]
            break
    # Clean up
    name = re.sub(r"[_-]", " ", name).strip()
    return name if name else "Unknown Candidate"
