"""Shortlist PPTX generator.

Takes structured candidate data + client/role info, returns branded PPTX bytes.
Uses the Infinitas shortlist template. Keeps table styles intact for proper
row backgrounds. Replaces candidate photos with uploads or a placeholder.
"""

import io
from copy import deepcopy
from datetime import datetime, date
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.oxml.ns import qn
from pptx.util import Emu


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "shortlist-template.pptx"
PLACEHOLDER_PATH = Path(__file__).parent.parent / "assets" / "photo-placeholder.png"

LOREM = (
    "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    "Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    "\x0b\x0b"
    "Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris "
    "nisi ut aliquip ex ea commodo consequat."
    "\x0b\x0b"
    "Duis aute irure dolor in reprehenderit in voluptate velit esse cillum "
    "dolore eu fugiat nulla pariatur."
)


def _calc_duration(start_str: str, end_str: str) -> str:
    """Calculate human-readable duration between two date strings.

    Accepts formats: 'MMM YYYY' (e.g. 'Jan 2020') or 'Present'.
    """
    if not start_str:
        return ""

    try:
        start = datetime.strptime(start_str, "%b %Y").date()
    except ValueError:
        return ""

    if not end_str or end_str.lower() == "present":
        end = date.today()
    else:
        try:
            end = datetime.strptime(end_str, "%b %Y").date()
        except ValueError:
            return ""

    total_months = (end.year - start.year) * 12 + end.month - start.month
    years, months = divmod(total_months, 12)

    if years == 0:
        return f"{months} month{'s' if months != 1 else ''}"
    elif months == 0:
        return f"{years} year{'s' if years != 1 else ''}"
    else:
        ys = "s" if years != 1 else ""
        ms = "s" if months != 1 else ""
        return f"{years} year{ys}, {months} month{ms}"


def _set_row_cell_text(row_elem, col_idx: int, text: str):
    """Set text in a cloned table row's cell via XML, preserving formatting."""
    cells = row_elem.findall(qn("a:tc"))
    if col_idx >= len(cells):
        return
    tc = cells[col_idx]
    txBody = tc.find(qn("a:txBody"))
    if txBody is None:
        return
    p = txBody.find(qn("a:p"))
    if p is None:
        return
    runs = p.findall(qn("a:r"))
    for extra in runs[1:]:
        p.remove(extra)
    r = p.find(qn("a:r"))
    if r is not None:
        t = r.find(qn("a:t"))
        if t is not None:
            t.text = text


def _set_detail_cell(cell, text: str):
    """Set a details table cell with proper line break handling.

    Inserts <a:br/> elements for \\x0b or \\n characters, and places
    all runs BEFORE <a:endParaRPr> so PowerPoint renders them.
    """
    p0 = cell.text_frame.paragraphs[0]
    p_elem = p0._p

    # Extract formatting from existing runs or endParaRPr
    rPr_template = None
    if p0.runs:
        rPr_elem = p0.runs[0]._r.find(qn("a:rPr"))
        if rPr_elem is not None:
            rPr_template = deepcopy(rPr_elem)
    if rPr_template is None:
        endRPr = p_elem.find(qn("a:endParaRPr"))
        if endRPr is not None:
            rPr_template = deepcopy(endRPr)
            rPr_template.tag = qn("a:rPr")
    if rPr_template is None:
        txBody_elem = p_elem.getparent()
        for other_p in txBody_elem.findall(qn("a:p")):
            for other_r in other_p.findall(qn("a:r")):
                rPr_found = other_r.find(qn("a:rPr"))
                if rPr_found is not None:
                    rPr_template = deepcopy(rPr_found)
                    break
            if rPr_template is not None:
                break

    # Clear existing runs and breaks
    for child in list(p_elem):
        if child.tag in (qn("a:r"), qn("a:br")):
            p_elem.remove(child)

    # Remove extra paragraphs
    txBody_elem = p_elem.getparent()
    for extra_p in list(txBody_elem.findall(qn("a:p")))[1:]:
        txBody_elem.remove(extra_p)

    # Insert new runs before endParaRPr
    endParaRPr = p_elem.find(qn("a:endParaRPr"))

    # Split on line break characters
    parts = text.replace("\n", "\x0b").split("\x0b")
    for j, part in enumerate(parts):
        if j > 0:
            br_elem = etree.Element(qn("a:br"))
            if endParaRPr is not None:
                endParaRPr.addprevious(br_elem)
            else:
                p_elem.append(br_elem)
        r_elem = etree.Element(qn("a:r"))
        if rPr_template is not None:
            r_elem.insert(0, deepcopy(rPr_template))
        t_elem = etree.SubElement(r_elem, qn("a:t"))
        t_elem.text = part
        if endParaRPr is not None:
            endParaRPr.addprevious(r_elem)
        else:
            p_elem.append(r_elem)


def _replace_picture(slide, old_shape, new_image_bytes: bytes):
    """Replace a Picture shape's image with new bytes, keeping position and size."""
    left = old_shape.left
    top = old_shape.top
    width = old_shape.width
    height = old_shape.height

    # Remove old picture
    sp = old_shape._element
    sp.getparent().remove(sp)

    # Add new picture at same position
    pic_stream = io.BytesIO(new_image_bytes)
    slide.shapes.add_picture(pic_stream, left, top, width, height)


def _clone_slide(prs: Presentation, slide_index: int) -> None:
    """Clone a slide and append it to the presentation."""
    import copy

    template_slide = prs.slides[slide_index]
    slide_layout = template_slide.slide_layout
    new_slide = prs.slides.add_slide(slide_layout)

    # Copy all shapes from template to new slide
    for shape in template_slide.shapes:
        el = copy.deepcopy(shape.element)
        new_slide.shapes._spTree.append(el)

    # Remove the default placeholder shapes that add_slide creates
    for ph in list(new_slide.placeholders):
        sp = ph._element
        sp.getparent().remove(sp)


def generate_shortlist(
    client_name: str,
    role_title: str,
    candidates: list[dict],
) -> bytes:
    """Generate a branded shortlist PPTX.

    Args:
        client_name: Client company name (e.g. "Unico")
        role_title: Role being recruited (e.g. "Chief Executive Officer")
        candidates: List of candidate dicts, each with:
            - name: str
            - career: list of dicts with keys: company, title, start_date,
              end_date, include (bool)
            - education_qualifications: str
            - notice_period: str
            - salary_expectation: str
            - notes: str (or empty for lorem ipsum)
            - use_lorem: bool
            - photo: bytes or None (optional candidate photo)

    Returns:
        PPTX file as bytes.
    """
    prs = Presentation(str(TEMPLATE_PATH))

    # Load placeholder photo
    placeholder_bytes = PLACEHOLDER_PATH.read_bytes() if PLACEHOLDER_PATH.exists() else None

    # --- Cover slide (slide 0) ---
    slide0 = prs.slides[0]
    for shape in slide0.shapes:
        if not shape.has_text_frame:
            continue
        for para in shape.text_frame.paragraphs:
            text = para.text.strip()
            if text == "COMMERCIAL":
                for run in para.runs:
                    run.text = role_title.upper().rsplit(" ", 1)[0] if " " in role_title else role_title.upper()
            elif text == "DIRECTOR":
                for run in para.runs:
                    run.text = role_title.upper().rsplit(" ", 1)[-1] if " " in role_title else ""
            elif "EVOLUTION HEALTHCARE" in text:
                for run in para.runs:
                    run.text = run.text.replace("EVOLUTION HEALTHCARE", client_name.upper())
            elif "Additional Candidates" in text:
                for i, run in enumerate(para.runs):
                    run.text = "SHORTLIST" if i == 0 else ""

    # --- Ensure enough candidate slides ---
    template_candidate_count = len(prs.slides) - 1  # subtract cover
    needed = len(candidates)

    while template_candidate_count < needed:
        _clone_slide(prs, 1)
        template_candidate_count += 1

    # --- Fill each candidate slide ---
    for cand_idx, cand in enumerate(candidates):
        slide = prs.slides[cand_idx + 1]

        # Filter career to only included rows
        career = [c for c in cand.get("career", []) if c.get("include", True)]

        # Get candidate photo (uploaded bytes or placeholder)
        photo_bytes = cand.get("photo") or placeholder_bytes

        for shape in slide.shapes:
            # Candidate name
            if shape.name == "TextBox 6":
                for para in shape.text_frame.paragraphs:
                    for i, run in enumerate(para.runs):
                        run.text = cand["name"] if i == 0 else ""

            # Career history table
            elif shape.name == "Table 7":
                table = shape.table
                tbl = table._tbl

                template_row_xml = None
                if len(tbl.tr_lst) > 1:
                    template_row_xml = deepcopy(tbl.tr_lst[1])

                while len(tbl.tr_lst) > 1:
                    tbl.remove(tbl.tr_lst[-1])

                if template_row_xml is not None:
                    prev_company = None
                    for entry in career:
                        new_row = deepcopy(template_row_xml)
                        company = entry.get("company", "")
                        title = entry.get("title", "")
                        start = entry.get("start_date", "")
                        end = entry.get("end_date", "")
                        duration = _calc_duration(start, end)

                        # Blank company if same as previous row
                        display_company = "" if company == prev_company else company
                        prev_company = company

                        values = [display_company, title, start, end, duration]
                        for col_i, val in enumerate(values):
                            _set_row_cell_text(new_row, col_i, val)
                        tbl.append(new_row)

            # Details table
            elif shape.name == "Table 2":
                table = shape.table
                edu_qual = cand.get("education_qualifications", "")
                detail_data = [
                    cand.get("notice_period", "") or "Not disclosed",
                    cand.get("salary_expectation", "") or "Not disclosed",
                    edu_qual,
                    "",  # Row 3 left empty — education_qualifications covers both
                ]
                for row_i in range(min(4, len(table.rows))):
                    _set_detail_cell(table.cell(row_i, 1), detail_data[row_i])

            # Notes
            elif shape.name == "Rectangle: Rounded Corners 8":
                if shape.has_text_frame:
                    tf = shape.text_frame
                    notes_text = LOREM if cand.get("use_lorem", False) else cand.get("notes", "") or LOREM
                    for p in tf.paragraphs:
                        for r in p.runs:
                            r.text = ""
                    done = False
                    for p in tf.paragraphs:
                        if p.runs and not done:
                            p.runs[0].text = notes_text
                            done = True

            # Replace candidate photo with upload or placeholder
            elif shape.shape_type == 13 and photo_bytes:
                _replace_picture(slide, shape, photo_bytes)

    # --- Remove extra candidate slides ---
    while len(prs.slides) > needed + 1:
        rId = prs.slides._sldIdLst[-1].get(qn("r:id"))
        prs.part.drop_rel(rId)
        prs.slides._sldIdLst.remove(prs.slides._sldIdLst[-1])

    # --- Save to bytes ---
    buf = io.BytesIO()
    prs.save(buf)
    buf.seek(0)
    return buf.getvalue()
