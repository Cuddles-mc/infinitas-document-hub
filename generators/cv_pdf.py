"""CV PDF generator.

Creates branded, redacted CV PDFs with an Infinitas cover page.
Handles both DOCX and PDF input formats.
"""

import io
import re
from pathlib import Path

from docx import Document
from fpdf import FPDF


FONT_NAME = "Helvetica"  # Built-in PDF font (Aptos not available in fpdf)

# Brand colours
BLUE = (0, 72, 153)       # #004899
DARK = (14, 40, 65)       # #0E2841
GREY = (55, 65, 81)       # #374151
LIGHT_GREY = (111, 111, 111)


def _create_cover_page(candidate_name: str, client_name: str) -> bytes:
    """Generate a branded cover page PDF.

    Layout matches the existing Infinitas CV cover page:
    - "CV OF [NAME]" centred on page
    - "Prepared for [Client]" below
    - Disclaimer footer at bottom
    """
    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.add_page()
    pdf.set_auto_page_break(auto=False)

    page_w = 210
    page_h = 297

    # --- "CV OF [NAME]" centred ---
    pdf.set_font(FONT_NAME, "B", 28)
    pdf.set_text_color(*DARK)

    title_text = f"CV OF {candidate_name.upper()}"
    title_y = page_h * 0.40  # 40% down the page
    pdf.set_y(title_y)
    pdf.cell(0, 14, title_text, align="C", new_x="LMARGIN", new_y="NEXT")

    # --- "Prepared for [Client]" ---
    pdf.set_font(FONT_NAME, "", 16)
    pdf.set_text_color(*GREY)
    pdf.ln(6)
    pdf.cell(0, 10, f"Prepared for {client_name}", align="C", new_x="LMARGIN", new_y="NEXT")

    # --- Disclaimer footer ---
    footer_y = page_h - 30
    pdf.set_y(footer_y)
    pdf.set_font(FONT_NAME, "", 6)
    pdf.set_text_color(*LIGHT_GREY)

    footer_lines = [
        "Infinitas Talent Limited  |  2 Princes Street, Auckland 1010  |  +64 9 218 6127  |  infinitas.co.nz",
        "This candidate is being represented by Infinitas Talent Limited.",
        "Our standard terms of business will apply. This document is private and confidential.",
    ]
    for line in footer_lines:
        pdf.cell(0, 3.5, line, align="C", new_x="LMARGIN", new_y="NEXT")

    return pdf.output()


def _redact_docx(docx_bytes: bytes) -> bytes:
    """Strip PII patterns from a DOCX file, preserving formatting.

    Removes: phone numbers, emails, URLs, addresses, references section.
    Returns cleaned DOCX bytes.
    """
    doc = Document(io.BytesIO(docx_bytes))

    # Regex patterns for PII
    phone_pattern = re.compile(
        r"(\+?\d{1,3}[\s.-]?)?\(?\d{1,4}\)?[\s.-]?\d{2,4}[\s.-]?\d{2,4}[\s.-]?\d{0,4}"
    )
    email_pattern = re.compile(r"\S+@\S+\.\S+")
    url_pattern = re.compile(r"https?://\S+|www\.\S+|linkedin\.com\S*", re.IGNORECASE)
    address_pattern = re.compile(
        r"\d+\s+[\w\s]+(?:street|st|road|rd|avenue|ave|drive|dr|lane|ln|crescent|cres|place|pl|way|terrace|tce)\b",
        re.IGNORECASE,
    )

    in_references = False

    for para in doc.paragraphs:
        text_lower = para.text.strip().lower()

        # Detect references section
        if text_lower in ("references", "referees", "references available upon request"):
            in_references = True

        # Clear everything in references section
        if in_references:
            for run in para.runs:
                run.text = ""
            continue

        # Strip PII from runs
        for run in para.runs:
            original = run.text
            cleaned = email_pattern.sub("", original)
            cleaned = url_pattern.sub("", cleaned)
            # Only strip phone patterns that look like actual phone numbers (7+ digits)
            for match in phone_pattern.finditer(cleaned):
                digits = re.sub(r"\D", "", match.group())
                if len(digits) >= 7:
                    cleaned = cleaned.replace(match.group(), "")
            cleaned = address_pattern.sub("", cleaned)
            run.text = cleaned.strip() if cleaned.strip() != original.strip() else original

    # Remove hyperlinks from relationships
    for rel in list(doc.part.rels.values()):
        if "hyperlink" in str(rel.reltype).lower():
            try:
                doc.part.rels.pop(rel.rId)
            except Exception:
                pass

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.getvalue()


def _merge_pdfs(cover_pdf: bytes, cv_pdf: bytes) -> bytes:
    """Merge cover page PDF with CV PDF."""
    import pypdf

    writer = pypdf.PdfWriter()

    # Add cover page
    cover_reader = pypdf.PdfReader(io.BytesIO(cover_pdf))
    writer.add_page(cover_reader.pages[0])

    # Add CV pages
    cv_reader = pypdf.PdfReader(io.BytesIO(cv_pdf))
    for page in cv_reader.pages:
        writer.add_page(page)

    buf = io.BytesIO()
    writer.write(buf)
    buf.seek(0)
    return buf.getvalue()


def generate_cv_pdf(
    candidate_name: str,
    client_name: str,
    cv_file_bytes: bytes,
    cv_filename: str,
    use_ai_redaction: bool = True,
) -> bytes:
    """Generate a branded, redacted CV PDF.

    Args:
        candidate_name: Candidate's full name
        client_name: Client company name
        cv_file_bytes: Raw uploaded file bytes
        cv_filename: Original filename (for format detection)
        use_ai_redaction: Whether to use AI for deeper redaction

    Returns:
        Final PDF bytes (cover page + redacted CV).
    """
    # Generate cover page
    cover_pdf = _create_cover_page(candidate_name, client_name)

    is_docx = cv_filename.lower().endswith(".docx")

    if is_docx:
        # Redact DOCX first (preserves formatting)
        redacted_docx = _redact_docx(cv_file_bytes)

        # Convert DOCX to PDF via MS Graph
        from ui import convert_docx_to_pdf
        cv_pdf = convert_docx_to_pdf(redacted_docx, cv_filename)
        if cv_pdf is None:
            raise RuntimeError(
                "DOCX to PDF conversion failed. "
                "Check MS Graph authentication."
            )
    else:
        # PDF input — use as-is (limited redaction possible)
        # Strip link annotations
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(cv_file_bytes))
        writer = pypdf.PdfWriter()
        for page in reader.pages:
            # Remove annotation links
            if "/Annots" in page:
                page[pypdf.generic.NameObject("/Annots")] = pypdf.generic.ArrayObject()
            writer.add_page(page)
        buf = io.BytesIO()
        writer.write(buf)
        buf.seek(0)
        cv_pdf = buf.getvalue()

    # Merge cover + CV
    return _merge_pdfs(cover_pdf, cv_pdf)
