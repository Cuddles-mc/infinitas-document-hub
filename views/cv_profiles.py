"""CV Profiles — build branded CV packs for a shortlist.

For each candidate: generate a branded cover page ("CV OF {NAME}" /
"Prepared for {COMPANY}"), convert to PDF via MS Graph, merge with the
uploaded candidate CV PDF, and produce a file named
"CV of {name} prepared for {company}.pdf".
"""

import io
import os
import re
import zipfile

import streamlit as st
from pypdf import PdfReader, PdfWriter

from ui import page_header, form_section


def render():
    page_header(
        "CV Profiles",
        "Branded cover page + candidate CV, merged into one PDF per candidate",
    )

    form_section("Client Company")
    st.markdown(
        """
        <div style="background:#fef3c7;border-left:4px solid #f59e0b;padding:0.75rem 1rem;
                    border-radius:0.375rem;margin-bottom:0.5rem;font-size:0.9rem;color:#78350f;">
          <strong>⚠ Double-check this name.</strong> It appears on <em>every</em> cover page
          and in <em>every</em> output filename. Spelling, capitalisation, and "Limited" vs
          "Ltd" all flow straight through to the client.
        </div>
        """,
        unsafe_allow_html=True,
    )
    company = st.text_input(
        "Client company name *",
        key="cvp_company",
        placeholder="Acme Holdings Limited",
        help="Used on every cover page and in the output filename. Must be exact.",
    )
    if company and company.strip():
        st.caption(f"Will appear as: **CV of [Candidate] prepared for {company.strip()}.pdf**")

    form_section("Candidate CVs")
    st.caption("Upload one PDF per candidate. You can remove files with the X next to each one.")
    uploaded = st.file_uploader(
        "Upload candidate CVs (PDF)",
        type=["pdf"],
        accept_multiple_files=True,
        key="cvp_uploader",
    )

    if not uploaded:
        st.info("Upload one or more candidate CVs to begin.")
        if "cvp_results" in st.session_state:
            del st.session_state["cvp_results"]
        return

    form_section(f"Candidate Names ({len(uploaded)})")
    st.caption("Edit names if the auto-fill is wrong — they appear on the cover page.")

    candidates = []
    for f in uploaded:
        default = _guess_name_from_filename(f.name)
        name = st.text_input(
            f.name,
            value=default,
            key=f"cvp_name_{f.file_id}",
        )
        candidates.append({"name": name.strip(), "file": f})

    st.divider()

    company_clean = (company or "").strip()
    all_named = all(c["name"] for c in candidates)

    build_clicked = st.button(
        "Build CV profiles",
        type="primary",
        width="stretch",
        disabled=(not company_clean or not all_named),
    )

    if not company_clean:
        st.caption("Enter a client company name to enable build.")
    elif not all_named:
        st.caption("Every candidate needs a name.")

    if build_clicked:
        _build_profiles(candidates, company_clean)

    if "cvp_results" in st.session_state:
        _render_results()


def _build_profiles(candidates: list[dict], company: str):
    items = [
        {
            "name": c["name"],
            "cv_bytes": c["file"].getvalue(),
            "cv_filename": c["file"].name,
        }
        for c in candidates
    ]
    st.session_state.cvp_results = build_profiles_from_items(items, company)


def build_profiles_from_items(items: list[dict], company: str) -> dict:
    """Reusable builder. Each item: {"name", "cv_bytes", "cv_filename"}.

    Returns {"files": {filename: bytes}, "errors": [str]}. Handles PDF and DOCX
    candidate CVs (DOCX is converted to PDF via Graph before merge).
    """
    from generators.cv_cover import generate_cover_docx
    from ms_auth import convert_docx_to_pdf_graph

    results = {"files": {}, "errors": []}
    progress = st.progress(0.0, text="Building CV profiles...")

    total = len(items)
    for i, item in enumerate(items):
        name = item["name"]
        cv_bytes = item["cv_bytes"]
        cv_filename = item.get("cv_filename", "")
        label = f"{i + 1}/{total}: {name}"
        progress.progress(i / total, text=f"{label} — generating cover...")

        try:
            cover_docx = generate_cover_docx(name, company)
        except Exception as e:
            results["errors"].append(f"{name}: cover generation failed — {e}")
            continue

        progress.progress((i + 0.33) / total, text=f"{label} — converting to PDF...")
        cover_pdf = convert_docx_to_pdf_graph(
            cover_docx, filename=f"CV Cover - {_safe(name)}.docx"
        )
        if not cover_pdf:
            results["errors"].append(
                f"{name}: PDF conversion failed (check Microsoft sign-in)."
            )
            continue

        # If the candidate CV is DOCX, convert it to PDF first
        cv_pdf_bytes = cv_bytes
        if cv_filename.lower().endswith(".docx"):
            progress.progress((i + 0.5) / total, text=f"{label} — converting CV to PDF...")
            cv_pdf_bytes = convert_docx_to_pdf_graph(
                cv_bytes, filename=f"CV - {_safe(name)}.docx"
            )
            if not cv_pdf_bytes:
                results["errors"].append(
                    f"{name}: CV DOCX→PDF conversion failed (check Microsoft sign-in)."
                )
                continue

        progress.progress((i + 0.66) / total, text=f"{label} — merging with CV...")
        try:
            merged = _merge_pdfs([cover_pdf, cv_pdf_bytes])
        except Exception as e:
            results["errors"].append(f"{name}: merge failed — {e}")
            continue

        filename = f"CV of {_safe(name)} prepared for {_safe(company)}.pdf"
        results["files"][filename] = merged

    progress.progress(1.0, text="Done")
    progress.empty()

    return results


def _render_results():
    results = st.session_state.cvp_results
    files = results["files"]
    errors = results["errors"]

    form_section("Download")

    if errors:
        for err in errors:
            st.error(err)

    if not files:
        st.warning("No files were produced.")
        return

    st.success(f"Built {len(files)} CV profile{'s' if len(files) != 1 else ''}.")

    for fname, fbytes in files.items():
        st.download_button(
            label=f"Download {fname}",
            data=fbytes,
            file_name=fname,
            mime="application/pdf",
            key=f"cvp_dl_{fname}",
        )

    if len(files) > 1:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, fbytes in files.items():
                zf.writestr(fname, fbytes)
        st.download_button(
            label="Download all (.zip)",
            data=zip_buf.getvalue(),
            file_name="CV Profiles.zip",
            mime="application/zip",
            type="primary",
            key="cvp_dl_zip",
        )


def _merge_pdfs(pdf_bytes_list: list[bytes]) -> bytes:
    writer = PdfWriter()
    for pdf_bytes in pdf_bytes_list:
        reader = PdfReader(io.BytesIO(pdf_bytes))
        for page in reader.pages:
            writer.add_page(page)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _guess_name_from_filename(filename: str) -> str:
    """Strip extension and common CV suffixes to guess a candidate name."""
    stem = os.path.splitext(filename)[0]
    stem = re.sub(r"[\-_]+", " ", stem)
    stem = re.sub(
        r"\s*\b(cv|resume|curriculum\s*vitae|profile)\b.*$",
        "",
        stem,
        flags=re.IGNORECASE,
    ).strip()
    return stem or os.path.splitext(filename)[0]


def _safe(text: str) -> str:
    """Strip characters that would break Windows filenames; collapse whitespace."""
    text = re.sub(r'[\\/:*?"<>|]+', " ", text)
    return re.sub(r"\s+", " ", text).strip()
