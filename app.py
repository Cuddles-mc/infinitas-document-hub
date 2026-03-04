"""Infinitas Document Hub - branded document generator for the team."""

import streamlit as st
from datetime import date, datetime

st.set_page_config(
    page_title="Infinitas Document Hub",
    page_icon="I",
    layout="wide",
)


# --- Auth Gate ---
def check_password():
    """Simple password gate for team access."""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("Infinitas Document Hub")
    password = st.text_input("Team password", type="password")
    if password:
        if password == st.secrets["APP_PASSWORD"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()


# --- Sidebar Navigation ---
DOCUMENT_TYPES = {
    "Reference Check": "reference_check",
    "Placement Letters": "placement_letters",
    "Assignment Confirmation (coming soon)": None,
    "CV Profile (coming soon)": None,
}

st.sidebar.title("Document Hub")
selected = st.sidebar.radio("Document type", list(DOCUMENT_TYPES.keys()))

# --- Header ---
st.title("Infinitas Document Hub")

# --- Reference Check Page ---
if DOCUMENT_TYPES[selected] == "reference_check":
    from generators.reference_check import generate_docx, QUESTIONS
    from ai import process_reference_transcript

    st.header("Reference Check")

    # Form fields
    col1, col2 = st.columns(2)
    with col1:
        candidate_name = st.text_input("Candidate name *")
        position = st.text_input("Role applied for *")
        completed_by = st.selectbox(
            "Completed by",
            ["Tate McClenaghan", "Jason Elston", "Kelsi Halliday", "Aimee"],
        )
    with col2:
        referee_name = st.text_input("Referee name *")
        referee_title = st.text_input("Referee current position")
        referee_previous = st.text_input("Referee previous position (optional)")

    transcript = st.text_area(
        "Paste Granola transcript",
        height=300,
        placeholder="Paste the full reference call transcript here...",
    )

    # --- Generate ---
    if st.button("Generate Reference", type="primary"):
        if not candidate_name or not position or not referee_name:
            st.error("Please fill in all required fields (marked with *).")
        elif not transcript.strip():
            st.error("Please paste the transcript.")
        else:
            with st.spinner("Processing transcript with AI..."):
                try:
                    answers = process_reference_transcript(
                        candidate_name=candidate_name,
                        position=position,
                        referee_name=referee_name,
                        referee_title=referee_title,
                        referee_previous=referee_previous,
                        transcript=transcript,
                    )
                    st.session_state.ref_answers = answers
                    st.session_state.ref_metadata = {
                        "candidate_name": candidate_name,
                        "position": position,
                        "referee_name": referee_name,
                        "referee_title": referee_title,
                        "referee_previous": referee_previous,
                        "completed_by": completed_by,
                        "reference_date": date.today().strftime("%d/%m/%Y"),
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing transcript: {e}")

    # --- Review & Edit ---
    if "ref_answers" in st.session_state:
        st.divider()
        st.subheader("Review & Edit Answers")
        st.caption("Edit any answer below before downloading the document.")

        answers = st.session_state.ref_answers
        edited_answers = {}

        for i, question in enumerate(QUESTIONS):
            key = str(i)
            current = answers.get(key, "")
            is_gap = current.startswith("[GAP]")

            label = f"Q{i+1}: {question}"
            if is_gap:
                label += "  ⚠️ NEEDS REVIEW"

            edited = st.text_area(
                label,
                value=current.replace("[GAP] ", ""),
                height=120 if len(current) > 200 else 80,
                key=f"answer_{i}",
            )
            edited_answers[key] = edited

        # --- Download ---
        st.divider()
        metadata = st.session_state.ref_metadata
        data = {**metadata, "answers": edited_answers}

        try:
            docx_bytes = generate_docx(data)
            filename = f"Reference Check for {metadata['candidate_name']} from {metadata['referee_name']}.docx"
            st.download_button(
                label="Download .docx",
                data=docx_bytes,
                file_name=filename,
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                type="primary",
            )
        except Exception as e:
            st.error(f"Error generating document: {e}")

# --- Placement Letters Page ---
elif DOCUMENT_TYPES.get(selected) == "placement_letters":
    from generators.placement_letters import generate_client_letter, generate_candidate_letter

    st.header("Placement Letters")

    # Form fields
    col1, col2 = st.columns(2)
    with col1:
        pl_consultant = st.selectbox(
            "Consultant",
            ["Jason Beith", "Tate McClenaghan", "Kelsi Flynn"],
        )
        pl_candidate_name = st.text_input("Candidate name *", key="pl_candidate")
        pl_candidate_address = st.text_area(
            "Candidate address",
            height=80,
            key="pl_candidate_addr",
            placeholder="123 Queen St\nAuckland 1010",
        )
        pl_position = st.text_input("Position title *", key="pl_position")
        pl_salary = st.text_input("Salary / package *", key="pl_salary", placeholder="$250,000 + KiwiSaver")
    with col2:
        pl_client_company = st.text_input("Client company *", key="pl_company")
        pl_client_contact = st.text_input("Client contact name *", key="pl_contact")
        pl_client_title = st.text_input("Client contact title", key="pl_contact_title")
        pl_client_address = st.text_area(
            "Client address",
            height=80,
            key="pl_client_addr",
            placeholder="456 Shortland St\nAuckland 1010",
        )
        pl_hiring_manager = st.text_input("Reporting manager", key="pl_manager")

    col3, col4 = st.columns(2)
    with col3:
        pl_start_date = st.date_input("Start date", key="pl_date")
        pl_location = st.text_input("Location of work", value="As agreed", key="pl_location")
    with col4:
        pl_guarantee = st.text_input("Guarantee period (client letter only)", value="3 months", key="pl_guarantee")

    st.divider()

    # Letter selection
    st.subheader("Output")
    lcol1, lcol2 = st.columns(2)
    with lcol1:
        st.caption("Which letters?")
        pl_gen_client = st.checkbox("Client Confirmation", value=True, key="pl_gen_client")
        pl_gen_candidate = st.checkbox("Candidate Confirmation", value=True, key="pl_gen_candidate")
    with lcol2:
        st.caption("Format")
        pl_fmt_docx = st.checkbox(".docx", value=True, key="pl_fmt_docx")
        pl_fmt_pdf = st.checkbox(".pdf", value=False, key="pl_fmt_pdf")

    # Generate
    if st.button("Generate Letters", type="primary", key="pl_generate"):
        # Validation
        missing = []
        if not pl_candidate_name:
            missing.append("Candidate name")
        if not pl_position:
            missing.append("Position title")
        if not pl_client_company:
            missing.append("Client company")
        if not pl_client_contact:
            missing.append("Client contact name")
        if not pl_salary:
            missing.append("Salary / package")
        if not pl_gen_client and not pl_gen_candidate:
            missing.append("At least one letter type")
        if not pl_fmt_docx and not pl_fmt_pdf:
            missing.append("At least one format")

        if missing:
            st.error(f"Please fill in: {', '.join(missing)}")
        else:
            # Format start date
            formatted_date = f"{pl_start_date.day} {pl_start_date.strftime('%B')} {pl_start_date.year}"
            letter_date = f"{datetime.now().day} {datetime.now().strftime('%B')} {datetime.now().year}"

            data = {
                "consultant": pl_consultant,
                "candidate_name": pl_candidate_name,
                "candidate_address": pl_candidate_address,
                "position": pl_position,
                "client_company": pl_client_company,
                "client_contact_name": pl_client_contact,
                "client_contact_title": pl_client_title,
                "client_address": pl_client_address,
                "start_date": formatted_date,
                "salary": pl_salary,
                "hiring_manager": pl_hiring_manager,
                "location_of_work": pl_location,
                "guarantee_period": pl_guarantee,
                "letter_date": letter_date,
            }

            generated = {}
            try:
                if pl_gen_client:
                    generated["client"] = generate_client_letter(data)
                if pl_gen_candidate:
                    generated["candidate"] = generate_candidate_letter(data)
                st.session_state.pl_generated = generated
                st.session_state.pl_data = data
                st.rerun()
            except Exception as e:
                st.error(f"Error generating letters: {e}")

    # Download section
    if "pl_generated" in st.session_state:
        st.divider()
        st.subheader("Download")
        data = st.session_state.pl_data
        candidate = data["candidate_name"]
        generated = st.session_state.pl_generated

        docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        pdf_mime = "application/pdf"

        for letter_type, docx_bytes in generated.items():
            label = "Client" if letter_type == "client" else "Candidate"
            base_name = f"Confirmation of Placement - {candidate} ({label})"

            dl_cols = st.columns(2)
            if pl_fmt_docx:
                with dl_cols[0]:
                    st.download_button(
                        label=f"Download {label} .docx",
                        data=docx_bytes,
                        file_name=f"{base_name}.docx",
                        mime=docx_mime,
                        key=f"dl_{letter_type}_docx",
                    )
            if pl_fmt_pdf:
                with dl_cols[1]:
                    # Convert docx bytes to PDF
                    try:
                        import tempfile
                        from docx2pdf import convert
                        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                            tmp.write(docx_bytes)
                            tmp_docx = tmp.name
                        tmp_pdf = tmp_docx.replace(".docx", ".pdf")
                        convert(tmp_docx, tmp_pdf)
                        with open(tmp_pdf, "rb") as f:
                            pdf_bytes = f.read()
                        import os
                        os.unlink(tmp_docx)
                        os.unlink(tmp_pdf)
                        st.download_button(
                            label=f"Download {label} .pdf",
                            data=pdf_bytes,
                            file_name=f"{base_name}.pdf",
                            mime=pdf_mime,
                            key=f"dl_{letter_type}_pdf",
                        )
                    except ImportError:
                        st.warning(f"PDF conversion not available (docx2pdf not installed). Download .docx instead.")
                    except Exception as e:
                        st.warning(f"PDF conversion failed: {e}. Download .docx instead.")

else:
    st.info("This document type is coming soon.")
