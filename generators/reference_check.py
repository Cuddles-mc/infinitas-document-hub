"""Reference check document generator.

Takes a data dict with metadata + 26 answers, returns branded .docx bytes.
"""

import io
import os
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml
from pathlib import Path


# Template path relative to project root
TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "reference-check-template.dotx"

FONT = "Arial"
FONT_SIZE = Pt(10)
Q_COLOUR = RGBColor(0x66, 0x66, 0x66)
A_COLOUR = RGBColor(0x00, 0x00, 0x00)

# The 26 reference check questions (used for display in UI)
QUESTIONS = [
    "What was your relationship to the candidate? Did they report into you?",
    "How long were they with the company? How long did they report to you?",
    "Why did the candidate leave the company?",
    "What were their main role and responsibilities?",
    "In relation to your expectations how would you rate their overall performance?",
    "How would you comment on their technical skills required to carry out their role?",
    "How would you comment on their work ethic?",
    "What are their main strengths?",
    "What are their main areas for development?",
    "What is their ability to meet deadlines?",
    "How would you comment on their decision-making ability?",
    "Did they manage a team? What was their management style / ability?",
    "Do they work well in the team / company with others?",
    "Were there ever any conflicts with any other team members?",
    "How did they manage external stakeholders?",
    "How would you describe their ability to deal with pressure?",
    "How would you describe their ability to cope with change?",
    "Have you ever had to question their integrity or honesty?",
    "How would you comment on their attendance? Any sick leave taken or attendance issues?",
    "Have you ever had to raise any behavioural or performance issues with the candidate? If so, what were the reasons and the outcome?",
    "Are you aware of any health condition or substance dependency or anything else that might affect their ability to do their job?",
    "If you had the opportunity, would you employ them in a similar role? Or at all?",
    "Would you recommend them for the role for which they are applying?",
    "Are we able to share this reference with the candidate?",
    "Are we able to share this reference with the client?",
    "Is there any additional information that you feel we should consider as part of our evaluation as to their suitability for this job or are there any other comments you would like to make?",
]


def _convert_dotx_to_docx_bytes(dotx_path: str) -> bytes:
    """Convert a .dotx template to .docx bytes by patching content type."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        with zipfile.ZipFile(dotx_path, 'r') as z:
            z.extractall(tmp_dir)

        ct_path = os.path.join(tmp_dir, '[Content_Types].xml')
        tree = ET.parse(ct_path)
        root = tree.getroot()
        ns = '{http://schemas.openxmlformats.org/package/2006/content-types}'
        for override in root.findall(f'{ns}Override'):
            ct = override.get('ContentType', '')
            if 'template.main+xml' in ct:
                override.set('ContentType',
                             'application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml')

        tree.write(ct_path, xml_declaration=True, encoding='UTF-8')

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zout:
            for root_dir, dirs, files in os.walk(tmp_dir):
                for f in files:
                    full = os.path.join(root_dir, f)
                    arcname = os.path.relpath(full, tmp_dir)
                    zout.write(full, arcname)
        return buf.getvalue()


def _set_font(run, bold=False, is_question=False):
    """Apply consistent font formatting to a run."""
    run.font.name = FONT
    run.font.size = FONT_SIZE
    run.font.bold = bold
    run.font.color.rgb = Q_COLOUR if is_question else A_COLOUR
    rPr = run._r.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rPr.append(parse_xml(
            f'<w:rFonts {nsdecls("w")} w:ascii="{FONT}" w:hAnsi="{FONT}" '
            f'w:eastAsia="{FONT}" w:cs="{FONT}"/>'
        ))


def generate_docx(data: dict) -> bytes:
    """Generate a branded reference check .docx from data dict.

    Args:
        data: Dict with keys: candidate_name, position, referee_name,
              referee_title, referee_previous, reference_date,
              completed_by, answers (dict of str index -> str answer)

    Returns:
        .docx file contents as bytes
    """
    answers = data["answers"]

    # Convert template to docx bytes, then load into python-docx
    docx_bytes = _convert_dotx_to_docx_bytes(str(TEMPLATE_PATH))
    doc = Document(io.BytesIO(docx_bytes))

    # --- Table 0: Metadata ---
    t0 = doc.tables[0]
    metadata_map = {
        0: data.get("reference_date", ""),
        1: data.get("candidate_name", ""),
        2: data.get("position", ""),
        4: data.get("referee_name", ""),
        5: data.get("referee_title", ""),
        6: data.get("referee_previous", ""),
    }
    for row_idx, value in metadata_map.items():
        if not value:
            continue
        cell = t0.rows[row_idx].cells[1]
        for p in cell.paragraphs:
            for run in p.runs:
                run.text = ""
        run = cell.paragraphs[0].add_run(value)
        _set_font(run)

    # --- Table 1: Questions and Answers ---
    table = doc.tables[1]
    for row_idx in range(len(table.rows)):
        str_idx = str(row_idx)
        if str_idx not in answers:
            continue

        cell = table.rows[row_idx].cells[0]
        question_text = cell.text.strip()

        for p in cell.paragraphs:
            p._element.getparent().remove(p._element)

        q_para = cell.add_paragraph()
        q_run = q_para.add_run(question_text)
        _set_font(q_run, bold=True, is_question=True)
        q_para.paragraph_format.space_after = Pt(4)

        blank = cell.add_paragraph()
        blank.paragraph_format.space_before = Pt(0)
        blank.paragraph_format.space_after = Pt(0)

        a_para = cell.add_paragraph()
        answer_text = answers[str_idx]
        paragraphs = answer_text.split("\n\n")
        first_run = a_para.add_run(paragraphs[0])
        _set_font(first_run, bold=False, is_question=False)
        a_para.paragraph_format.space_before = Pt(0)
        a_para.paragraph_format.space_after = Pt(6)

        for extra in paragraphs[1:]:
            extra_para = cell.add_paragraph()
            extra_run = extra_para.add_run(extra)
            _set_font(extra_run, bold=False, is_question=False)
            extra_para.paragraph_format.space_before = Pt(0)
            extra_para.paragraph_format.space_after = Pt(6)

        trail = cell.add_paragraph()
        trail.paragraph_format.space_before = Pt(0)
        trail.paragraph_format.space_after = Pt(0)

    # --- Table 2: Completed by ---
    t2 = doc.tables[2]
    cell_cb = t2.rows[0].cells[0]
    for p in cell_cb.paragraphs:
        p.text = ""
    completed_by = data.get("completed_by", "Tate McClenaghan")
    r1 = cell_cb.paragraphs[0].add_run(f"Reference completed by: {completed_by}")
    _set_font(r1, bold=True, is_question=True)
    p2 = cell_cb.add_paragraph()
    r2 = p2.add_run(f"Date: {data.get('reference_date', '')}")
    _set_font(r2, is_question=True)

    # Save to bytes
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()
