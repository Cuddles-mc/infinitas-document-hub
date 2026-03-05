"""Infinitas Document Hub - branded document generator for the team."""

import io
import os
import platform
import subprocess
import tempfile
import streamlit as st
from datetime import date, datetime


def convert_docx_to_pdf(docx_bytes: bytes) -> bytes | None:
    """Convert .docx bytes to .pdf bytes. Works on Windows (Word) and Linux (LibreOffice)."""
    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_docx = os.path.join(tmp_dir, "doc.docx")
            with open(tmp_docx, "wb") as f:
                f.write(docx_bytes)

            if platform.system() == "Windows":
                import pythoncom
                from docx2pdf import convert
                pythoncom.CoInitialize()
                try:
                    tmp_pdf = os.path.join(tmp_dir, "doc.pdf")
                    convert(tmp_docx, tmp_pdf)
                finally:
                    pythoncom.CoUninitialize()
            else:
                # Linux — use LibreOffice headless
                subprocess.run(
                    ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", tmp_dir, tmp_docx],
                    check=True, capture_output=True, timeout=30,
                )
                tmp_pdf = os.path.join(tmp_dir, "doc.pdf")

            if os.path.exists(tmp_pdf):
                with open(tmp_pdf, "rb") as f:
                    return f.read()
    except Exception:
        return None
    return None

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

    # --- Spreadsheet Upload ---
    uploaded_xlsx = st.file_uploader(
        "Upload Candidate Details.xlsx (optional — pre-fills the form)",
        type=["xlsx"],
        key="pl_upload",
    )

    if uploaded_xlsx and "pl_xlsx_parsed" not in st.session_state:
        try:
            from openpyxl import load_workbook
            import io as _io

            wb = load_workbook(_io.BytesIO(uploaded_xlsx.read()), read_only=True, data_only=True)
            ws = wb.active

            section_headers = {"Candidate", "Role", "Placement", "Referee 1", "Referee 2"}
            field_map = {
                ("Candidate", "Full Name"): "candidate_name",
                ("Candidate", "Address Line 1"): "candidate_address_line_1",
                ("Candidate", "Address Line 2"): "candidate_address_line_2",
                ("Role", "Position"): "position",
                ("Role", "Client Company"): "client_company",
                ("Role", "Client Contact"): "client_contact_name",
                ("Role", "Consultant"): "consultant_raw",
                ("Placement", "Start Date"): "start_date",
                ("Placement", "Salary (Permanent)"): "salary",
                ("Placement", "Pay Rate (Contract)"): "pay_rate",
                ("Placement", "Reporting Manager"): "reporting_manager",
                ("Placement", "Client Address Line 1"): "client_address_line_1",
                ("Placement", "Client Address Line 2"): "client_address_line_2",
            }

            parsed = {}
            current_section = None
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=2):
                label = str(row[0].value or "").strip()
                value = row[1].value
                if isinstance(value, datetime):
                    value = f"{value.day} {value.strftime('%B')} {value.year}"
                else:
                    value = str(value).strip() if value is not None else ""
                if label in section_headers and not value:
                    current_section = label
                    continue
                if not label or not current_section:
                    continue
                key = (current_section, label)
                if key in field_map:
                    parsed[field_map[key]] = value
            wb.close()

            # Resolve consultant name
            consultant_map = {
                "jason": "Jason Beith", "jason beith": "Jason Beith",
                "kelsi": "Kelsi Flynn", "kelsi flynn": "Kelsi Flynn",
                "tate": "Tate McClenaghan", "tate mcclenaghan": "Tate McClenaghan",
            }
            raw_consultant = parsed.get("consultant_raw", "")
            parsed["consultant"] = consultant_map.get(raw_consultant.lower(), "Tate McClenaghan")

            # Combine address lines
            parsed["candidate_address"] = "\n".join(
                l for l in [parsed.get("candidate_address_line_1", ""), parsed.get("candidate_address_line_2", "")] if l
            )
            parsed["client_address"] = "\n".join(
                l for l in [parsed.get("client_address_line_1", ""), parsed.get("client_address_line_2", "")] if l
            )

            # Use salary or pay rate
            if not parsed.get("salary"):
                parsed["salary"] = parsed.get("pay_rate", "")

            # Set widget keys directly in session state so form pre-fills
            st.session_state.pl_candidate = parsed.get("candidate_name", "")
            st.session_state.pl_candidate_addr = parsed.get("candidate_address", "")
            st.session_state.pl_position = parsed.get("position", "")
            st.session_state.pl_salary = parsed.get("salary", "")
            st.session_state.pl_company = parsed.get("client_company", "")
            st.session_state.pl_contact = parsed.get("client_contact_name", "")
            st.session_state.pl_client_addr = parsed.get("client_address", "")
            st.session_state.pl_manager = parsed.get("reporting_manager", "")

            # Consultant selectbox uses index
            consultant_options = ["Jason Beith", "Tate McClenaghan", "Kelsi Flynn"]
            st.session_state.pl_consultant_idx = (
                consultant_options.index(parsed["consultant"])
                if parsed.get("consultant") in consultant_options
                else 1
            )

            st.session_state.pl_xlsx_parsed = True
            st.rerun()
        except Exception as e:
            st.error(f"Error reading spreadsheet: {e}")

    # Form fields
    col1, col2 = st.columns(2)
    consultant_options = ["Jason Beith", "Tate McClenaghan", "Kelsi Flynn"]
    consultant_idx = st.session_state.get("pl_consultant_idx", 1)

    with col1:
        pl_consultant = st.selectbox(
            "Consultant",
            consultant_options,
            index=consultant_idx,
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

        company = data["client_company"]

        # Build all files for individual + zip download
        all_files = {}  # name -> bytes

        for letter_type, docx_bytes in generated.items():
            if letter_type == "client":
                label = "Client Letter"
                base_name = f"{candidate} Placement Confirmation for {company}"
            else:
                label = "Candidate Letter"
                base_name = f"Placement Confirmation {candidate} at {company}"

            if pl_fmt_docx:
                all_files[f"{base_name}.docx"] = docx_bytes

            if pl_fmt_pdf:
                pdf_bytes = convert_docx_to_pdf(docx_bytes)
                if pdf_bytes:
                    all_files[f"{base_name}.pdf"] = pdf_bytes
                else:
                    st.warning(f"PDF conversion failed for {label}. Download .docx instead.")

            # Individual download buttons
            dl_cols = st.columns(2)
            docx_key = f"{base_name}.docx"
            pdf_key = f"{base_name}.pdf"
            if docx_key in all_files:
                with dl_cols[0]:
                    st.download_button(
                        label=f"Download {label} .docx",
                        data=all_files[docx_key],
                        file_name=docx_key,
                        mime=docx_mime,
                        key=f"dl_{letter_type}_docx",
                    )
            if pdf_key in all_files:
                with dl_cols[1]:
                    st.download_button(
                        label=f"Download {label} .pdf",
                        data=all_files[pdf_key],
                        file_name=pdf_key,
                        mime=pdf_mime,
                        key=f"dl_{letter_type}_pdf",
                    )

        # Download All as ZIP
        if len(all_files) > 1:
            import zipfile
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, fbytes in all_files.items():
                    zf.writestr(fname, fbytes)
            st.divider()
            st.download_button(
                label="Download All (.zip)",
                data=zip_buffer.getvalue(),
                file_name=f"Placement Letters - {candidate}.zip",
                mime="application/zip",
                type="primary",
                key="dl_all_zip",
            )

else:
    st.info("This document type is coming soon.")
