"""Contractor Agreement document generator.

Takes a data dict with Schedule 1 fields, returns branded .docx bytes.
Supports Sole Trader and Limited Company templates.
"""

import io
from pathlib import Path
from docx import Document


TEMPLATES = {
    "sole_trader": Path(__file__).parent.parent / "templates" / "contractor-agreement-sole-trader.docx",
    "ltd_company": Path(__file__).parent.parent / "templates" / "contractor-agreement-ltd-company.docx",
}


def _replace_in_para(para, old: str, new: str):
    """Replace text in a paragraph, preserving formatting as much as possible.

    Strategy:
    1. Try run-by-run replacement (best: preserves all formatting)
    2. If text spans runs, find the spanning range, clear middle runs,
       and update first/last runs to contain the replacement.
    """
    if old not in para.text:
        return False

    # Strategy 1: text is entirely within one run
    for run in para.runs:
        if old in run.text:
            run.text = run.text.replace(old, new)
            return True

    # Strategy 2: text spans multiple runs
    full_text = ""
    run_ranges = []  # [(start_char, end_char, run_idx)]
    for idx, run in enumerate(para.runs):
        start = len(full_text)
        full_text += run.text
        run_ranges.append((start, len(full_text), idx))

    match_start = full_text.find(old)
    if match_start == -1:
        return False
    match_end = match_start + len(old)

    # Find which runs the match starts and ends in
    first_run_idx = None
    last_run_idx = None
    for start, end, idx in run_ranges:
        if start <= match_start < end:
            first_run_idx = idx
        if start < match_end <= end:
            last_run_idx = idx

    if first_run_idx is None or last_run_idx is None:
        # Fallback: rebuild from paragraph text (loses formatting)
        new_text = full_text.replace(old, new)
        for run in para.runs[1:]:
            run.text = ""
        para.runs[0].text = new_text
        return True

    # Reconstruct: prefix + replacement in first run,
    # suffix in last run, clear middle runs
    first_start = run_ranges[first_run_idx][0]
    last_end = run_ranges[last_run_idx][1]

    prefix = full_text[first_start:match_start]
    suffix = full_text[match_end:last_end]

    first_run = para.runs[first_run_idx]
    last_run = para.runs[last_run_idx]

    if first_run_idx == last_run_idx:
        first_run.text = prefix + new + suffix
    else:
        first_run.text = prefix + new
        last_run.text = suffix
        # Clear middle runs
        for i in range(first_run_idx + 1, last_run_idx):
            para.runs[i].text = ""

    return True


def _fill_sole_trader(doc: Document, data: dict):
    """Fill Schedule 1 fields for Sole Trader template."""
    replacements = {
        "Date of Agreement:": f"Date of Agreement: {data.get('date_of_agreement', '')}",
        "Nominated Client:": f"Nominated Client: {data.get('nominated_client', '')}",
        "Role: Commencement Date:": f"Role: {data.get('role', '')}  Commencement Date: {data.get('commencement_date', '')}",
        "Hours of Work: Contract Rate:": f"Hours of Work: {data.get('hours_of_work', '')}  Contract Rate: {data.get('contract_rate', '')}",
        "End Date:": f"End Date: {data.get('end_date', '')}",
        "Notice Period:": f"Notice Period: {data.get('notice_period', '')}",
    }
    travel = data.get("travel_expenses", "Upon authorisation by the Nominated Client")
    replacements["Other/Travel Expenses:\tUpon authorisation by the Nominated Client"] = f"Other/Travel Expenses:\t{travel}"

    for para in doc.paragraphs:
        for old, new in replacements.items():
            _replace_in_para(para, old, new)


def _fill_ltd_company(doc: Document, data: dict):
    """Fill Schedule 1 fields for Ltd Company template."""
    replacements = {
        "Date of Agreement:": f"Date of Agreement: {data.get('date_of_agreement', '')}",
        "Name of Providers Company:": f"Name of Providers Company: {data.get('provider_company', '')}",
        "Trading as if Applicable:": f"Trading as if Applicable: {data.get('trading_as', '')}",
        "Registered Address:": f"Registered Address: {data.get('registered_address', '')}",
        "Company NO. /NZBN:": f"Company NO. /NZBN: {data.get('company_nzbn', '')}",
        "Name of Individual Contractor:": f"Name of Individual Contractor: {data.get('individual_contractor', '')}",
        "IRD Number:": f"IRD Number: {data.get('ird_number', '')}",
        "Nominated Bank Account Number:": f"Nominated Bank Account Number: {data.get('bank_account', '')}",
        "Nominated Client:": f"Nominated Client: {data.get('nominated_client', '')}",
        "Role:": f"Role: {data.get('role', '')}",
        "Hours of Work:": f"Hours of Work: {data.get('hours_of_work', '')}",
    }

    gst_reg = data.get("gst_registered", False)
    gst_num = data.get("gst_number", "")
    replacements["GST Registered: Yes / No    GST Number:"] = (
        f"GST Registered: {'Yes' if gst_reg else 'No'}    GST Number: {gst_num}"
    )

    replacements["Commencement Date:                    End Date:"] = (
        f"Commencement Date: {data.get('commencement_date', '')}                    End Date: {data.get('end_date', '')}"
    )
    replacements["Contract Rate:                    Notice Period:"] = (
        f"Contract Rate: {data.get('contract_rate', '')}                    Notice Period: {data.get('notice_period', '')}"
    )

    travel = data.get("travel_expenses", "Upon authorisation by the Nominated Client")
    replacements["Other/Travel Expenses:  Upon authorisation by the Nominated Client"] = (
        f"Other/Travel Expenses:  {travel}"
    )

    for para in doc.paragraphs:
        for old, new in replacements.items():
            _replace_in_para(para, old, new)


def generate_docx(data: dict) -> bytes:
    """Generate a Contractor Agreement .docx from form data.

    data must include:
        contractor_type: "sole_trader" or "ltd_company"
        Plus all Schedule 1 fields.
    Returns .docx file as bytes.
    """
    ctype = data.get("contractor_type", "sole_trader")
    template_path = TEMPLATES[ctype]
    doc = Document(str(template_path))

    if ctype == "sole_trader":
        _fill_sole_trader(doc, data)
    else:
        _fill_ltd_company(doc, data)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
