"""Shared UI components for Document Hub pages.

PandaDoc/Proposify-inspired patterns:
- Step flow indicators (Fill -> Review -> Download)
- Consistent form sections with visual hierarchy
- Shared download and draft resume blocks
"""

import io
import zipfile
import streamlit as st
from datetime import date


# ---------------------------------------------------------------------------
# Step flow — visual progress indicator
# ---------------------------------------------------------------------------
def step_flow(steps: list[str], current: int):
    """Render a horizontal step indicator.

    Args:
        steps: List of step labels, e.g. ["Fill Details", "Review", "Download"]
        current: 0-based index of the current step
    """
    cols = st.columns(len(steps))
    for i, (col, label) in enumerate(zip(cols, steps)):
        with col:
            if i < current:
                # Completed
                st.markdown(
                    f'<div style="text-align:center; padding:0.5rem 0;">'
                    f'<div style="display:inline-block; width:28px; height:28px; '
                    f'border-radius:50%; background:#10B981; color:white; '
                    f'line-height:28px; font-size:14px; font-weight:600;">&#10003;</div>'
                    f'<div style="font-size:0.8rem; color:#10B981; font-weight:500; margin-top:4px;">'
                    f'{label}</div></div>',
                    unsafe_allow_html=True,
                )
            elif i == current:
                # Active
                st.markdown(
                    f'<div style="text-align:center; padding:0.5rem 0;">'
                    f'<div style="display:inline-block; width:28px; height:28px; '
                    f'border-radius:50%; background:var(--primary-color, #004899); color:white; '
                    f'line-height:28px; font-size:14px; font-weight:600;">{i+1}</div>'
                    f'<div style="font-size:0.8rem; color:var(--primary-color, #004899); '
                    f'font-weight:600; margin-top:4px;">{label}</div></div>',
                    unsafe_allow_html=True,
                )
            else:
                # Upcoming
                st.markdown(
                    f'<div style="text-align:center; padding:0.5rem 0;">'
                    f'<div style="display:inline-block; width:28px; height:28px; '
                    f'border-radius:50%; background:#E5E7EB; color:#9CA3AF; '
                    f'line-height:28px; font-size:14px; font-weight:600;">{i+1}</div>'
                    f'<div style="font-size:0.8rem; color:#9CA3AF; margin-top:4px;">'
                    f'{label}</div></div>',
                    unsafe_allow_html=True,
                )
    st.markdown("")


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------
def page_header(title: str, subtitle: str = ""):
    """Render a consistent page header."""
    st.markdown(f"## {title}")
    if subtitle:
        st.caption(subtitle)


# ---------------------------------------------------------------------------
# Form section headers
# ---------------------------------------------------------------------------
def form_section(title: str):
    """Render a styled form section divider."""
    st.markdown(
        f'<p style="font-size: 0.85rem; font-weight: 600; '
        f'text-transform: uppercase; letter-spacing: 0.06em; '
        f'color: var(--primary-color, #004899); '
        f'margin: 1.5rem 0 0.75rem 0; padding-bottom: 0.4rem; '
        f'border-bottom: 2px solid var(--primary-color, #004899);">'
        f'{title}</p>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def validate_required(fields: dict[str, str]) -> list[str]:
    """Return list of missing required field labels."""
    return [label for label, value in fields.items() if not value]


def show_validation_error(missing: list[str]):
    st.error(f"Please fill in: {', '.join(missing)}")


# ---------------------------------------------------------------------------
# Download block
# ---------------------------------------------------------------------------
def download_block(
    files: dict[str, bytes],
    zip_name: str = "Documents",
):
    """Render download buttons. Adds zip if multiple files."""
    docx_mime = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    pdf_mime = "application/pdf"

    for fname, fbytes in files.items():
        mime = pdf_mime if fname.endswith(".pdf") else docx_mime
        st.download_button(
            label=f"Download {fname}",
            data=fbytes,
            file_name=fname,
            mime=mime,
            key=f"dl_{fname}",
        )

    if len(files) > 1:
        zip_buf = io.BytesIO()
        with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for fname, fbytes in files.items():
                zf.writestr(fname, fbytes)
        st.download_button(
            label="Download All (.zip)",
            data=zip_buf.getvalue(),
            file_name=f"{zip_name}.zip",
            mime="application/zip",
            type="primary",
            key="dl_all_zip",
        )


# ---------------------------------------------------------------------------
# Draft resume
# ---------------------------------------------------------------------------
def draft_resume_block(
    user_email: str,
    doc_type: str,
    restore_callback,
) -> bool:
    """Show draft resume UI if a saved draft exists.

    Returns True if a draft is pending (caller should st.stop()).
    """
    from drafts import load_draft

    check_key = f"_{doc_type}_checked"
    pending_key = f"_{doc_type}_pending"

    if check_key not in st.session_state:
        draft = load_draft(user_email, doc_type)
        st.session_state[check_key] = True
        if draft:
            st.session_state[pending_key] = draft

    if pending_key not in st.session_state:
        return False

    d = st.session_state[pending_key]
    updated = d.get("updated_at", "")[:10]
    st.info(f"You have a saved draft from {updated}.")
    c1, c2 = st.columns(2)
    with c1:
        if st.button("Resume draft", type="primary", key=f"{doc_type}_resume"):
            restore_callback(d.get("form_data", {}))
            del st.session_state[pending_key]
            st.rerun()
    with c2:
        if st.button("Start fresh", key=f"{doc_type}_fresh"):
            del st.session_state[pending_key]
            st.rerun()
    return True


# ---------------------------------------------------------------------------
# PDF conversion helper
# ---------------------------------------------------------------------------
def convert_docx_to_pdf(docx_bytes: bytes, filename: str = "document.docx"):
    """Convert .docx to PDF via MS Graph. Returns bytes or None."""
    from ms_auth import convert_docx_to_pdf_graph
    return convert_docx_to_pdf_graph(docx_bytes, filename)


def build_files_dict(
    generated: dict[str, bytes],
    name_map: dict[str, str],
    fmt_docx: bool,
    fmt_pdf: bool,
) -> dict[str, bytes]:
    """Build {filename: bytes} dict with optional PDF conversion."""
    files = {}
    for key, docx_bytes in generated.items():
        base_name = name_map.get(key, key)
        if fmt_docx:
            files[f"{base_name}.docx"] = docx_bytes
        if fmt_pdf:
            pdf = convert_docx_to_pdf(docx_bytes)
            if pdf:
                files[f"{base_name}.pdf"] = pdf
            else:
                st.warning(f"PDF conversion failed for {key}.")
    return files
