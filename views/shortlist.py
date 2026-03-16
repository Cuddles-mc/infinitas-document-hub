"""Shortlist Generator — upload CVs, review extracted data, download branded PPTX."""

import streamlit as st
from ui import page_header, step_flow, form_section


def render():
    page_header("Shortlist Generator", "Upload CVs to create a branded shortlist presentation")

    # Determine current step
    has_candidates = "sl_candidates" in st.session_state
    has_pptx = "sl_pptx_bytes" in st.session_state
    current_step = 2 if has_pptx else (1 if has_candidates else 0)
    step_flow(["Upload CVs", "Review & Edit", "Download"], current_step)

    if has_pptx:
        _render_download()
    elif has_candidates:
        _render_review()
    else:
        _render_upload()


# ---------------------------------------------------------------------------
# Step 1: Upload
# ---------------------------------------------------------------------------
def _render_upload():
    form_section("Assignment Details")
    col1, col2 = st.columns(2)
    with col1:
        client_name = st.text_input("Client name *", key="sl_client_name_input")
    with col2:
        role_title = st.text_input("Role title *", key="sl_role_title_input")

    form_section("Upload CVs")
    uploaded_files = st.file_uploader(
        "Upload candidate CVs (PDF or DOCX)",
        type=["pdf", "docx"],
        accept_multiple_files=True,
        key="sl_cv_upload",
    )

    if uploaded_files:
        st.caption(f"{len(uploaded_files)} file(s) selected")

    st.markdown("")
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        extract = st.button(
            "Extract candidate data",
            type="primary",
            use_container_width=True,
            disabled=not uploaded_files,
        )

    if extract:
        if not client_name or not role_title:
            st.error("Please fill in client name and role title.")
            return
        if not uploaded_files:
            st.error("Please upload at least one CV.")
            return

        candidates = []
        progress = st.progress(0, text="Extracting CVs...")

        for i, f in enumerate(uploaded_files):
            progress.progress(
                (i) / len(uploaded_files),
                text=f"Extracting {f.name}...",
            )

            try:
                cv_text = _extract_text(f)
                if not cv_text.strip():
                    st.warning(f"Could not extract text from {f.name}")
                    continue

                from ai import extract_cv_data
                data = extract_cv_data(cv_text)

                # Add include checkbox default and source filename
                for entry in data.get("career", []):
                    entry["include"] = True
                data["source_file"] = f.name
                data["notes"] = ""
                data["use_lorem"] = True
                candidates.append(data)

            except Exception as e:
                st.error(f"Error processing {f.name}: {e}")

        progress.progress(1.0, text="Done!")

        if candidates:
            st.session_state.sl_candidates = candidates
            st.session_state.sl_client_name = client_name
            st.session_state.sl_role_title = role_title
            st.rerun()
        else:
            st.error("No candidates could be extracted.")


def _extract_text(uploaded_file) -> str:
    """Extract plain text from an uploaded PDF or DOCX file."""
    name = uploaded_file.name.lower()
    data = uploaded_file.read()

    if name.endswith(".pdf"):
        return _extract_pdf_text(data)
    elif name.endswith(".docx"):
        return _extract_docx_text(data)
    return ""


def _extract_pdf_text(data: bytes) -> str:
    """Extract text from PDF bytes."""
    import io
    try:
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(data))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n".join(text_parts)
    except ImportError:
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(data))
            text_parts = []
            for page in reader.pages:
                text_parts.append(page.extract_text() or "")
            return "\n".join(text_parts)
        except ImportError:
            raise ImportError("Install pypdf or PyPDF2: pip install pypdf")


def _extract_docx_text(data: bytes) -> str:
    """Extract text from DOCX bytes."""
    import io
    from docx import Document
    doc = Document(io.BytesIO(data))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


# ---------------------------------------------------------------------------
# Step 2: Review & Edit
# ---------------------------------------------------------------------------
def _render_review():
    # Back button
    if st.button("< Back to upload"):
        del st.session_state["sl_candidates"]
        st.rerun()

    client_name = st.session_state.sl_client_name
    role_title = st.session_state.sl_role_title
    st.info(f"**{role_title}** at **{client_name}** — {len(st.session_state.sl_candidates)} candidate(s)")

    candidates = st.session_state.sl_candidates

    for idx, cand in enumerate(candidates):
        with st.expander(f"**{cand.get('name', 'Unknown')}** ({cand.get('source_file', '')})", expanded=True):
            _render_candidate_editor(idx, cand)

    # Add manual candidate
    st.divider()
    if st.button("+ Add candidate manually"):
        candidates.append({
            "name": "",
            "career": [],
            "education_qualifications": "",
            "notice_period": "",
            "salary_expectation": "",
            "notes": "",
            "use_lorem": True,
            "source_file": "Manual entry",
        })
        st.rerun()

    # Generate button
    st.markdown("")
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        generate = st.button(
            "Generate Shortlist PPTX",
            type="primary",
            use_container_width=True,
        )

    if generate:
        # Validate
        valid_candidates = [c for c in candidates if c.get("name", "").strip()]
        if not valid_candidates:
            st.error("At least one candidate needs a name.")
            return

        with st.spinner("Generating PPTX..."):
            try:
                from generators.shortlist_pptx import generate_shortlist
                pptx_bytes = generate_shortlist(
                    client_name=client_name,
                    role_title=role_title,
                    candidates=valid_candidates,
                )
                filename = f"{role_title} Shortlist prepared for {client_name} by Infinitas.pptx"
                st.session_state.sl_pptx_bytes = pptx_bytes
                st.session_state.sl_pptx_filename = filename
                st.rerun()
            except Exception as e:
                st.error(f"Error generating PPTX: {e}")
                import traceback
                st.code(traceback.format_exc())


def _render_candidate_editor(idx: int, cand: dict):
    """Render the editable form for a single candidate."""

    # Name
    cand["name"] = st.text_input(
        "Candidate name",
        value=cand.get("name", ""),
        key=f"cand_name_{idx}",
    )

    # Career history with checkboxes
    form_section("Career History")

    career = cand.get("career", [])
    if career:
        for ci, entry in enumerate(career):
            cols = st.columns([0.5, 3, 3, 1.5, 1.5, 1.5])
            with cols[0]:
                entry["include"] = st.checkbox(
                    "Inc",
                    value=entry.get("include", True),
                    key=f"career_inc_{idx}_{ci}",
                    label_visibility="collapsed",
                )
            with cols[1]:
                entry["company"] = st.text_input(
                    "Company",
                    value=entry.get("company", ""),
                    key=f"career_co_{idx}_{ci}",
                    label_visibility="collapsed" if ci > 0 else "visible",
                )
            with cols[2]:
                entry["title"] = st.text_input(
                    "Title",
                    value=entry.get("title", ""),
                    key=f"career_title_{idx}_{ci}",
                    label_visibility="collapsed" if ci > 0 else "visible",
                )
            with cols[3]:
                entry["start_date"] = st.text_input(
                    "Start",
                    value=entry.get("start_date", ""),
                    key=f"career_start_{idx}_{ci}",
                    label_visibility="collapsed" if ci > 0 else "visible",
                )
            with cols[4]:
                entry["end_date"] = st.text_input(
                    "End",
                    value=entry.get("end_date", ""),
                    key=f"career_end_{idx}_{ci}",
                    label_visibility="collapsed" if ci > 0 else "visible",
                )
            with cols[5]:
                if ci == 0:
                    st.caption("Delete")
                if st.button("X", key=f"career_del_{idx}_{ci}"):
                    career.pop(ci)
                    st.rerun()
    else:
        st.caption("No career entries. Add one below.")

    if st.button("+ Add career entry", key=f"add_career_{idx}"):
        career.append({
            "company": "",
            "title": "",
            "start_date": "",
            "end_date": "Present",
            "include": True,
        })
        st.rerun()

    # Education & Qualifications
    form_section("Education & Qualifications")
    cand["education_qualifications"] = st.text_area(
        "Education and professional qualifications",
        value=cand.get("education_qualifications", ""),
        height=100,
        key=f"cand_edu_{idx}",
        label_visibility="collapsed",
        placeholder="e.g. Bachelor of Commerce (Finance), University of Auckland\nChartered Accountant (CA), CAANZ",
    )

    # Details
    form_section("Details")
    col1, col2 = st.columns(2)
    with col1:
        cand["notice_period"] = st.text_input(
            "Notice period",
            value=cand.get("notice_period", ""),
            key=f"cand_notice_{idx}",
            placeholder="e.g. Available immediately, 4 weeks",
        )
    with col2:
        cand["salary_expectation"] = st.text_input(
            "Salary expectation",
            value=cand.get("salary_expectation", ""),
            key=f"cand_salary_{idx}",
            placeholder="e.g. $250,000 - $280,000",
        )

    # Photo
    form_section("Candidate Photo")
    photo_file = st.file_uploader(
        "Upload photo (optional — placeholder used if empty)",
        type=["png", "jpg", "jpeg"],
        key=f"cand_photo_{idx}",
    )
    if photo_file:
        cand["photo"] = photo_file.read()
        st.image(cand["photo"], width=150)
    else:
        cand["photo"] = None
        st.caption("No photo uploaded — placeholder will be used. You can swap it in PowerPoint later.")

    # Notes
    form_section("Consultant Notes")
    cand["use_lorem"] = st.checkbox(
        "No notes — use placeholder (lorem ipsum)",
        value=cand.get("use_lorem", True),
        key=f"cand_lorem_{idx}",
    )

    if not cand["use_lorem"]:
        cand["notes"] = st.text_area(
            "Notes",
            value=cand.get("notes", ""),
            height=200,
            key=f"cand_notes_{idx}",
            label_visibility="collapsed",
            placeholder="Write your assessment of this candidate...",
        )

        # Proofread button
        col_pr, _ = st.columns([1, 2])
        with col_pr:
            if st.button("Proofread notes", key=f"proofread_{idx}"):
                notes_text = cand.get("notes", "")
                if notes_text.strip():
                    with st.spinner("Proofreading..."):
                        try:
                            from ai import proofread_notes
                            corrected = proofread_notes(notes_text)
                            st.session_state[f"proofread_result_{idx}"] = corrected
                        except Exception as e:
                            st.error(f"Proofreading failed: {e}")

        # Show proofread result
        proofread_key = f"proofread_result_{idx}"
        if proofread_key in st.session_state:
            corrected = st.session_state[proofread_key]
            st.markdown("**Proofread version:**")
            st.text_area(
                "Corrected",
                value=corrected,
                height=200,
                key=f"proofread_preview_{idx}",
                label_visibility="collapsed",
                disabled=True,
            )
            col_accept, col_reject, _ = st.columns([1, 1, 2])
            with col_accept:
                if st.button("Accept", key=f"accept_proof_{idx}", type="primary"):
                    cand["notes"] = corrected
                    del st.session_state[proofread_key]
                    st.rerun()
            with col_reject:
                if st.button("Keep original", key=f"reject_proof_{idx}"):
                    del st.session_state[proofread_key]
                    st.rerun()


# ---------------------------------------------------------------------------
# Step 3: Download
# ---------------------------------------------------------------------------
def _render_download():
    # Back button
    if st.button("< Back to review"):
        del st.session_state["sl_pptx_bytes"]
        del st.session_state["sl_pptx_filename"]
        st.rerun()

    client_name = st.session_state.sl_client_name
    role_title = st.session_state.sl_role_title
    candidates = st.session_state.sl_candidates
    filename = st.session_state.sl_pptx_filename

    st.success(f"Shortlist generated: **{role_title}** at **{client_name}**")

    # Summary
    form_section("Summary")
    for cand in candidates:
        included_roles = sum(1 for c in cand.get("career", []) if c.get("include", True))
        st.markdown(f"- **{cand.get('name', 'Unknown')}** — {included_roles} career entries")

    st.markdown("")
    pptx_mime = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
    st.download_button(
        label="Download Shortlist (.pptx)",
        data=st.session_state.sl_pptx_bytes,
        file_name=filename,
        mime=pptx_mime,
        type="primary",
    )

    st.caption("The PPTX is fully editable — you can adjust fonts, layout, and content in PowerPoint.")

    # Start over
    st.divider()
    if st.button("Create another shortlist"):
        for key in list(st.session_state.keys()):
            if key.startswith("sl_") or key.startswith("cand_") or key.startswith("career_") or key.startswith("proofread"):
                del st.session_state[key]
        st.rerun()
