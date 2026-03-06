# Document Hub Phase 2 — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add T&Cs generator, Contractor Agreement generator, draft persistence, and Adobe Sign integration to the Document Hub Streamlit app.

**Architecture:** Template-based document generation (same pattern as existing placement_letters.py and reference_check.py). Each generator is a module in `generators/` that takes a data dict and returns .docx bytes. Draft persistence via a Supabase `doc_hub_drafts` table with auto-save/load. Adobe Sign integration as a shared module that embeds text tags and pushes PDFs via API.

**Tech Stack:** Streamlit, python-docx, Supabase (REST API via requests), Adobe Sign API v6 (OAuth), msal/requests (existing).

**Design doc:** `docs/plans/2026-03-06-doc-hub-phase2-design.md`

---

## Task 1: Copy templates into repo

**Files:**
- Create: `templates/terms-conditions.docx`
- Create: `templates/contractor-agreement-sole-trader.docx`
- Create: `templates/contractor-agreement-ltd-company.docx`

**Step 1: Copy the three template files**

```bash
cp "C:/Users/Tate McClenaghan/OneDrive - Infinitas Talent/Day to Day/Templates/Finance and Admin/Terms of Business/Master copies/Infinitas Talent - Terms and Conditions.docx" templates/terms-conditions.docx

cp "C:/Users/Tate McClenaghan/OneDrive - Infinitas Talent/Day to Day/Templates/Document Templates/Placement and Contract Templates/Assignment Confirmations[Contracts]/Contractor agreements 2025 (NEW)/New Infinitas Documents/Contractor Agreement Sole Trader.docx" templates/contractor-agreement-sole-trader.docx

cp "C:/Users/Tate McClenaghan/OneDrive - Infinitas Talent/Day to Day/Templates/Document Templates/Placement and Contract Templates/Assignment Confirmations[Contracts]/Contractor agreements 2025 (NEW)/New Infinitas Documents/Contractor Agreement Limited Company.docx" templates/contractor-agreement-ltd-company.docx
```

**Step 2: Verify templates load**

```bash
py -c "from docx import Document; [Document(f'templates/{t}') for t in ['terms-conditions.docx','contractor-agreement-sole-trader.docx','contractor-agreement-ltd-company.docx']]; print('All templates load OK')"
```

Expected: `All templates load OK`

**Step 3: Commit**

```bash
git add templates/
git commit -m "Add T&Cs and Contractor Agreement templates"
```

---

## Task 2: Draft persistence module (`drafts.py`)

**Files:**
- Create: `drafts.py`

**Context:** This module handles auto-saving and loading form state to Supabase. Uses the Supabase REST API directly (no SDK dependency). Credentials are in `secrets.toml`. Users never see any database references.

**Step 1: Create the Supabase migration**

Run this SQL in Supabase SQL Editor (project `ytdshfuuxpmawtusuogu`):

```sql
CREATE TABLE doc_hub_drafts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_email TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    form_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_email, doc_type)
);

-- Auto-delete drafts older than 30 days
CREATE OR REPLACE FUNCTION delete_expired_drafts() RETURNS void AS $$
    DELETE FROM doc_hub_drafts WHERE updated_at < now() - interval '30 days';
$$ LANGUAGE sql;
```

**Step 2: Add Supabase credentials to secrets.toml**

Add to `.streamlit/secrets.toml`:
```toml
SUPABASE_URL = "https://ytdshfuuxpmawtusuogu.supabase.co"
SUPABASE_SERVICE_KEY = "..."  # service_role key from Supabase dashboard
```

Update `.streamlit/secrets.toml.example`:
```toml
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SERVICE_KEY = "your-service-role-key"
```

**Step 3: Write `drafts.py`**

```python
"""Draft persistence for Document Hub via Supabase.

Auto-saves form state so users can resume later.
Invisible to users — no database references in UI.
"""

import json
from datetime import datetime, timezone
import requests
import streamlit as st


def _headers():
    return {
        "apikey": st.secrets["SUPABASE_SERVICE_KEY"],
        "Authorization": f"Bearer {st.secrets['SUPABASE_SERVICE_KEY']}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base_url():
    return f"{st.secrets['SUPABASE_URL']}/rest/v1/doc_hub_drafts"


def save_draft(user_email: str, doc_type: str, form_data: dict) -> None:
    """Upsert a draft. Silently fails on error."""
    try:
        requests.post(
            _base_url(),
            headers={**_headers(), "Prefer": "resolution=merge-duplicates,return=representation"},
            json={
                "user_email": user_email,
                "doc_type": doc_type,
                "form_data": form_data,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
            timeout=5,
        )
    except Exception:
        pass


def load_draft(user_email: str, doc_type: str) -> dict | None:
    """Load a draft if one exists. Returns form_data dict or None."""
    try:
        resp = requests.get(
            _base_url(),
            headers=_headers(),
            params={
                "user_email": f"eq.{user_email}",
                "doc_type": f"eq.{doc_type}",
                "select": "form_data,updated_at",
            },
            timeout=5,
        )
        rows = resp.json()
        if rows and len(rows) > 0:
            return rows[0]
        return None
    except Exception:
        return None


def delete_draft(user_email: str, doc_type: str) -> None:
    """Delete a draft after successful generation."""
    try:
        requests.delete(
            _base_url(),
            headers=_headers(),
            params={
                "user_email": f"eq.{user_email}",
                "doc_type": f"eq.{doc_type}",
            },
            timeout=5,
        )
    except Exception:
        pass


def cleanup_expired() -> None:
    """Delete drafts older than 30 days. Call on app load."""
    try:
        cutoff = datetime.now(timezone.utc).isoformat()
        requests.delete(
            _base_url(),
            headers=_headers(),
            params={"updated_at": f"lt.{cutoff}"},
            timeout=5,
        )
    except Exception:
        pass
```

**Step 4: Commit**

```bash
git add drafts.py .streamlit/secrets.toml.example
git commit -m "Add draft persistence module (Supabase)"
```

---

## Task 3: Contractor Agreement generator (`generators/contractor_agreement.py`)

**Files:**
- Create: `generators/contractor_agreement.py`

**Context:** Simpler of the two generators. Template fill — no clause toggling. Two templates (Sole Trader / Ltd Company) selected by `contractor_type` field. Fill Schedule 1 fields by finding and replacing text in paragraphs.

**Step 1: Write the generator**

```python
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
    """Replace text in a paragraph, preserving first run formatting."""
    if old in para.text:
        for run in para.runs:
            if old in run.text:
                run.text = run.text.replace(old, new)
                return True
        # Fallback: text spans multiple runs — rebuild
        full = para.text
        if old in full:
            new_text = full.replace(old, new)
            for run in para.runs[1:]:
                run.text = ""
            para.runs[0].text = new_text
            return True
    return False


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
    # Other/Travel has a tab character
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

    # GST registered toggle
    gst_reg = data.get("gst_registered", False)
    gst_num = data.get("gst_number", "")
    replacements["GST Registered: Yes / No    GST Number:"] = (
        f"GST Registered: {'Yes' if gst_reg else 'No'}    GST Number: {gst_num}"
    )

    # Fields with paired values on one line
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
```

**Step 2: Test manually**

```bash
py -c "
from generators.contractor_agreement import generate_docx
data = {
    'contractor_type': 'sole_trader',
    'date_of_agreement': '6 March 2026',
    'nominated_client': 'Acme Corp',
    'role': 'Senior Developer',
    'commencement_date': '1 April 2026',
    'end_date': '30 September 2026',
    'hours_of_work': '40 hours per week',
    'contract_rate': '\$120 per hour + GST',
    'notice_period': '2 weeks',
}
result = generate_docx(data)
with open('test_contractor.docx', 'wb') as f:
    f.write(result)
print(f'Generated: {len(result)} bytes')
"
```

Open `test_contractor.docx` and verify Schedule 1 fields are filled correctly.

Repeat for `contractor_type: "ltd_company"` with the extra fields.

**Step 3: Commit**

```bash
git add generators/contractor_agreement.py
git commit -m "Add Contractor Agreement generator (Sole Trader + Ltd Company)"
```

---

## Task 4: T&Cs generator (`generators/terms_conditions.py`)

**Files:**
- Create: `generators/terms_conditions.py`

**Context:** Most complex generator. Needs to: fill client name, toggle service type sections on/off, re-number clauses and cross-references, rewrite Schedule 1 fee text, update Guarantee Period definition, optionally append signature block.

The template has Heading 1 paragraphs as clause markers. Sections between headings are removed when toggled off.

**Key paragraph indices in `terms-conditions.docx`:**
- Table 1 row 0 cell 1: `[PARTY 2]` — client name
- Para 52: Guarantee Period definition — contains "three (3) calendar months"
- Heading 1 paragraphs mark clause starts — remove from heading to next heading
- Para 343+: Schedule 1 content

**Clause heading text (for matching):**
```
"PLACEMENT FEE - PERMANENT OR FIXED TERM WORKER SERVICES"  → clause 4
"LIABILITY TO PAY A PLACEMENT FEE"                          → clause 5
"FEES – CONTRACTOR OR TEMPORARY WORKER SERVICES"           → clause 6
"FEES FOR FURTHER CONTRACTING OR EMPLOYMENT..."            → clause 7
"FEES - RETAINED ASSIGNMENT AND EXECUTIVE SEARCH"          → clause 8
```

**Cross-references to update (10 total):**
```python
CROSS_REFS = {
    64: "clause 5 and 6",
    66: "clause 10",
    74: "clause 3.1",
    96: "clause 17",
    118: "clause 4",
    153: "clause 7.1",
    155: "clause 7.1",
    194: "clause 10.1",
    291: "clause 5",
    299: "clause 17.3",
}
```

**Step 1: Write the generator**

```python
"""Terms & Conditions document generator.

Takes a data dict with service type toggles and fee details,
returns branded .docx bytes with only the relevant clauses.
"""

import io
import re
from copy import deepcopy
from pathlib import Path
from docx import Document
from docx.shared import Pt, RGBColor
from docx.oxml.ns import qn


TEMPLATE_PATH = Path(__file__).parent.parent / "templates" / "terms-conditions.docx"

# Clause heading text -> clause number in the original template
CLAUSE_HEADINGS = {
    "DEFINITIONS AND INTERPRETATION": 1,
    "TERM": 2,
    "RIGHT OF RENEWAL": 3,
    "PLACEMENT FEE": 4,
    "LIABILITY TO PAY A PLACEMENT FEE": 5,
    "CONTRACTOR OR TEMPORARY WORKER SERVICES": 6,
    "FEES FOR FURTHER CONTRACTING": 7,
    "RETAINED ASSIGNMENT AND EXECUTIVE SEARCH": 8,
    "EXPENSES": 9,
    "PLACEMENT GUARANTEE": 10,
    "CLIENT OBLIGATIONS": 11,
    "INFINITAS TALENT OBLIGATIONS": 12,
    "LIMITATION OF LIABILITY": 13,
    "GST": 14,
    "ANTI-CORRUPTION": 15,
    "CONFIDENTIALITY AND PRIVACY": 16,
    "TERMINATION": 17,
    "CONSEQUENCES OF EXPIRY OR TERMINATION": 18,
    "GENERAL PROVISIONS": 19,
    "SCHEDULE 1": 20,
}

# Which clauses to remove per service type toggle
REMOVABLE = {
    "perm": [4, 5],       # Placement Fee + Liability to Pay
    "contract": [6, 7],   # Contractor/Temp Fees + Further Contracting
    "exec": [8],          # Retained/Exec Search Fees
}

# Guarantee period text variants
GUARANTEE_TEXT = {
    3: "three (3) calendar months",
    6: "six (6) calendar months",
    12: "twelve (12) calendar months",
}


def _find_heading_ranges(doc):
    """Map each Heading 1 paragraph to its clause number and index range.

    Returns list of (clause_num, start_idx, end_idx) where end_idx is
    exclusive (the index of the next Heading 1 or end of document).
    """
    ranges = []
    heading_indices = []

    for i, para in enumerate(doc.paragraphs):
        if para.style and para.style.name == "Heading 1":
            text = para.text.strip().upper()
            for key, num in CLAUSE_HEADINGS.items():
                if key in text:
                    heading_indices.append((num, i))
                    break

    for idx, (num, start) in enumerate(heading_indices):
        if idx + 1 < len(heading_indices):
            end = heading_indices[idx + 1][1]
        else:
            end = len(doc.paragraphs)
        ranges.append((num, start, end))

    return ranges


def _remove_paragraphs(doc, indices_to_remove: set):
    """Remove paragraphs by index (sets text to empty, removes from XML)."""
    body = doc.element.body
    to_remove = []
    for i, para in enumerate(doc.paragraphs):
        if i in indices_to_remove:
            to_remove.append(para._element)
    for elem in to_remove:
        body.remove(elem)


def _build_clause_map(removed_clauses: set) -> dict:
    """Build mapping of old clause number -> new clause number."""
    all_clauses = list(range(1, 21))
    remaining = [c for c in all_clauses if c not in removed_clauses]
    return {old: new for new, old in enumerate(remaining, 1)}


def _update_cross_references(doc, clause_map: dict):
    """Update all 'clause N' references in the document."""
    pattern = re.compile(r'(clause[s]?\s+)(\d+)(\.\d+)?', re.IGNORECASE)

    def replace_ref(match):
        prefix = match.group(1)
        old_num = int(match.group(2))
        sub = match.group(3) or ""
        new_num = clause_map.get(old_num, old_num)
        return f"{prefix}{new_num}{sub}"

    for para in doc.paragraphs:
        if "clause" in para.text.lower():
            for run in para.runs:
                if "clause" in run.text.lower():
                    run.text = pattern.sub(replace_ref, run.text)


def _update_guarantee_definition(doc, months: int):
    """Update the Guarantee Period definition text."""
    old = "three (3) calendar months"
    new = GUARANTEE_TEXT.get(months, f"{months} calendar months")
    for para in doc.paragraphs:
        if old in para.text:
            for run in para.runs:
                if old in run.text:
                    run.text = run.text.replace(old, new)
                    return
            # Fallback: spans runs
            full = para.text.replace(old, new)
            for run in para.runs[1:]:
                run.text = ""
            para.runs[0].text = full
            return


def _fill_client_name(doc, client_name: str):
    """Replace [PARTY 2] in Table 1 with the client company name."""
    if len(doc.tables) >= 2:
        cell = doc.tables[1].rows[0].cells[1]
        for para in cell.paragraphs:
            for run in para.runs:
                if "[PARTY 2]" in run.text:
                    run.text = run.text.replace("[PARTY 2]", client_name)
                    return
            if "[PARTY 2]" in para.text:
                para.text = para.text.replace("[PARTY 2]", client_name)
                return


def _rewrite_schedule_1(doc, data: dict):
    """Rewrite the Schedule 1 fee text based on enabled service types."""
    # Find Schedule 1 heading
    sched_start = None
    for i, para in enumerate(doc.paragraphs):
        if para.style and para.style.name == "Heading 1" and "SCHEDULE" in para.text.upper():
            sched_start = i
            break

    if sched_start is None:
        return

    # Clear all paragraphs after the heading
    for i in range(sched_start + 1, len(doc.paragraphs)):
        para = doc.paragraphs[i]
        for run in para.runs[1:]:
            run.text = ""
        if para.runs:
            para.runs[0].text = ""

    # Build new schedule text
    entries = []

    if data.get("perm_enabled", True):
        pct = data.get("perm_fee_pct", 18)
        basis = data.get("perm_basis", "total salary package")
        structure = data.get("perm_structure", "retained")
        guarantee = data.get("guarantee_months", 3)

        if data.get("perm_structure") == "fixed_fee":
            fee_text = f"Permanent Fees: A fixed fee of {data.get('perm_fixed_fee', 'TBC')}."
        else:
            fee_text = f"Permanent Fees: {pct}% based on the candidate\u2019s {basis}."

        if structure == "retained":
            fee_text += (
                " Unless otherwise stated, Infinitas Talent uses an industry standard "
                "retained fee structure and is invoiced in three instalments. One third on "
                "acceptance of the assignment, one third on presentation of the shortlist "
                f"and one third on placement. The placement guarantee is {guarantee} months."
            )
        elif structure == "contingent":
            fee_text += (
                f" Invoiced on placement. The placement guarantee is {guarantee} months."
            )

        entries.append(fee_text)

        # Fixed term
        ft_text = (
            f"Fixed Term Contract Fees: {pct}% Fees will be calculated on the candidates "
            f"{basis} Pro-Rata for the length of the fixed term placement (calculated in months). "
            "The minimum fee period to engage a fixed term candidate is six months. "
            f"The fixed term placement guarantee is {guarantee} months."
        )
        entries.append(ft_text)

    if data.get("contract_enabled", False):
        margin = data.get("contract_margin_pct", 25)
        entries.append(
            f"Contracting Fees: Infinitas Talent charges contract fees on either an hourly "
            f"or daily basis as agreed with you the client. Margin percentages on contracting "
            f"assignments are {margin}%."
        )

    if data.get("exec_enabled", False):
        pct = data.get("exec_fee_pct", 25)
        basis = data.get("exec_basis", "total salary package")

        if data.get("exec_structure") == "fixed_fee":
            exec_text = f"Executive Search Fees: A fixed fee of {data.get('exec_fixed_fee', 'TBC')}."
        else:
            exec_text = (
                f"Executive Search Fees: For Executive Recruitment Infinitas Talent\u2019s "
                f"fee is {pct}% of the candidate\u2019s {basis}. Infinitas Talent uses an "
                "industry standard retained fee structure and is invoiced in three instalments. "
                "One third on acceptance of the assignment, one third on presentation of the "
                "shortlist and one third on placement."
            )
        exec_text += (
            "\nExecutive Search Recruitment is defined as senior/executive leadership or "
            "specialised positions where a customised advertising and/or search process is "
            "undertaken on an exclusive basis."
        )
        entries.append(exec_text)

    # Contract buy-out (always included if contract or perm is on)
    if data.get("contract_enabled", False) or data.get("perm_enabled", True):
        entries.append(
            "Contract Buy out: For temporary or contract candidates, who are offered "
            "permanent positions with the client, a Pro-Rata fee will be calculated for a "
            "period of up to twelve months, with a minimum period of six months to be charged "
            "on acceptance of the engagement or employment by the client."
        )

    # GST note always
    entries.append(
        "All Fees quoted exclude \u201cGST\u201d Goods and Services Tax. GST will be "
        "added to final invoices sent out by Infinitas Talent."
    )

    # Write entries into the available paragraphs after schedule heading
    for idx, text in enumerate(entries):
        para_idx = sched_start + 1 + (idx * 2)  # every other para (blank between)
        if para_idx < len(doc.paragraphs):
            para = doc.paragraphs[para_idx]
            if para.runs:
                para.runs[0].text = text
            else:
                para.text = text


def _add_signature_block(doc, include_infinitas: bool, include_client: bool, adobe_sign: bool):
    """Append signature block table at the end of the document."""
    if not include_infinitas and not include_client:
        return

    doc.add_paragraph("")  # spacer

    rows_needed = 0
    if include_infinitas:
        rows_needed += 1
    if include_client:
        rows_needed += 1

    table = doc.add_table(rows=rows_needed * 2, cols=3)

    row_idx = 0
    if include_infinitas:
        cells = table.rows[row_idx].cells
        cells[0].text = "Signature" if not adobe_sign else "{{Sig_es_:signer1:signature}}"
        cells[1].text = "Name"
        cells[2].text = "Date" if not adobe_sign else "{{Dte_es_:signer1:date}}"
        label_cells = table.rows[row_idx + 1].cells
        label_cells[0].text = "Signed for and on behalf of Infinitas Talent Limited"
        row_idx += 2

    if include_client:
        signer = "signer2" if include_infinitas else "signer1"
        cells = table.rows[row_idx].cells
        cells[0].text = "Signature" if not adobe_sign else f"{{{{Sig_es_:{signer}:signature}}}}"
        cells[1].text = "Name"
        cells[2].text = "Date" if not adobe_sign else f"{{{{Dte_es_:{signer}:date}}}}"
        label_cells = table.rows[row_idx + 1].cells
        label_cells[0].text = "Signed for and on behalf of the Client"


def generate_docx(data: dict) -> bytes:
    """Generate T&Cs .docx from form data.

    data keys:
        client_name: str
        date: str
        perm_enabled: bool (default True)
        contract_enabled: bool
        exec_enabled: bool
        perm_fee_pct: int
        perm_basis: str ("base salary" or "total salary package")
        perm_structure: str ("retained", "contingent", "fixed_fee")
        perm_fixed_fee: str (if structure is fixed_fee)
        contract_margin_pct: int
        exec_fee_pct: int
        exec_basis: str
        exec_structure: str
        exec_fixed_fee: str
        guarantee_months: int (3, 6, or 12)
        sig_infinitas: bool
        sig_client: bool
        adobe_sign: bool
    """
    doc = Document(str(TEMPLATE_PATH))

    # 1. Fill client name
    _fill_client_name(doc, data.get("client_name", ""))

    # 2. Update guarantee definition
    _update_guarantee_definition(doc, data.get("guarantee_months", 3))

    # 3. Determine which clauses to remove
    clauses_to_remove = set()
    if not data.get("perm_enabled", True):
        clauses_to_remove.update(REMOVABLE["perm"])
    if not data.get("contract_enabled", False):
        clauses_to_remove.update(REMOVABLE["contract"])
    if not data.get("exec_enabled", False):
        clauses_to_remove.update(REMOVABLE["exec"])

    # 4. Find heading ranges and collect paragraph indices to remove
    if clauses_to_remove:
        ranges = _find_heading_ranges(doc)
        indices_to_remove = set()
        for clause_num, start, end in ranges:
            if clause_num in clauses_to_remove:
                for i in range(start, end):
                    indices_to_remove.add(i)

        # Remove paragraphs (must do before re-numbering)
        _remove_paragraphs(doc, indices_to_remove)

    # 5. Re-number clauses and update cross-references
    clause_map = _build_clause_map(clauses_to_remove)
    _update_cross_references(doc, clause_map)

    # 6. Rewrite Schedule 1
    _rewrite_schedule_1(doc, data)

    # 7. Add signature block
    _add_signature_block(
        doc,
        data.get("sig_infinitas", False),
        data.get("sig_client", False),
        data.get("adobe_sign", False),
    )

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
```

**Step 2: Test manually**

```bash
py -c "
from generators.terms_conditions import generate_docx
data = {
    'client_name': 'Test Company Ltd',
    'perm_enabled': True,
    'contract_enabled': False,
    'exec_enabled': True,
    'perm_fee_pct': 20,
    'perm_basis': 'base salary',
    'perm_structure': 'retained',
    'exec_fee_pct': 25,
    'exec_basis': 'total salary package',
    'exec_structure': 'retained',
    'guarantee_months': 6,
    'sig_infinitas': True,
    'sig_client': True,
    'adobe_sign': False,
}
result = generate_docx(data)
with open('test_tcs.docx', 'wb') as f:
    f.write(result)
print(f'Generated: {len(result)} bytes')
"
```

Open `test_tcs.docx` and verify:
- Client name filled in Table 1
- Guarantee definition says "six (6) calendar months"
- Contractor/Temp clauses (6, 7) removed
- Clause numbers re-sequenced (no gaps)
- Cross-references updated
- Schedule 1 has Permanent + Exec Search fees only
- Signature block at end

**Step 3: Commit**

```bash
git add generators/terms_conditions.py
git commit -m "Add T&Cs generator with clause toggling and re-numbering"
```

---

## Task 5: Adobe Sign integration (`adobe_sign.py`)

**Files:**
- Create: `adobe_sign.py`

**Context:** Shared module used by both generators. Pushes a PDF to Adobe Sign via REST API. Text tags embedded during generation handle signature field placement. Requires OAuth credentials in secrets.toml.

**Step 1: Add secrets**

Add to `.streamlit/secrets.toml`:
```toml
ADOBE_SIGN_CLIENT_ID = "..."
ADOBE_SIGN_CLIENT_SECRET = "..."
ADOBE_SIGN_REFRESH_TOKEN = "..."
ADOBE_SIGN_API_BASE = "https://api.au1.adobesign.com/api/rest/v6"
```

**Step 2: Write `adobe_sign.py`**

```python
"""Adobe Sign integration for Document Hub.

Uploads PDFs and sends for e-signature via Adobe Sign API v6.
Text tags embedded in the document during generation are automatically
converted to signature fields by Adobe Sign.
"""

import requests
import streamlit as st


def _get_access_token() -> str:
    """Exchange refresh token for an access token."""
    resp = requests.post(
        "https://api.au1.adobesign.com/oauth/v2/refresh",
        data={
            "refresh_token": st.secrets["ADOBE_SIGN_REFRESH_TOKEN"],
            "client_id": st.secrets["ADOBE_SIGN_CLIENT_ID"],
            "client_secret": st.secrets["ADOBE_SIGN_CLIENT_SECRET"],
            "grant_type": "refresh_token",
        },
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def upload_document(pdf_bytes: bytes, filename: str = "document.pdf") -> str:
    """Upload a PDF as a transient document. Returns the transient document ID."""
    token = _get_access_token()
    base = st.secrets["ADOBE_SIGN_API_BASE"]

    resp = requests.post(
        f"{base}/transientDocuments",
        headers=_headers(token),
        files={"File": (filename, pdf_bytes, "application/pdf")},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["transientDocumentId"]


def send_for_signature(
    transient_doc_id: str,
    agreement_name: str,
    signers: list[dict],
) -> dict:
    """Create an agreement and send for signature.

    signers: list of {"email": "...", "order": 1} dicts.
    Returns {"agreement_id": "...", "status": "OUT_FOR_SIGNATURE"}.
    """
    token = _get_access_token()
    base = st.secrets["ADOBE_SIGN_API_BASE"]

    participant_sets = []
    for signer in signers:
        participant_sets.append({
            "memberInfos": [{"email": signer["email"]}],
            "order": signer.get("order", 1),
            "role": "SIGNER",
        })

    payload = {
        "name": agreement_name,
        "participantSetsInfo": participant_sets,
        "signatureType": "ESIGN",
        "state": "IN_PROCESS",
        "fileInfos": [{"transientDocumentId": transient_doc_id}],
    }

    resp = requests.post(
        f"{base}/agreements",
        headers={**_headers(token), "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    resp.raise_for_status()
    data = resp.json()
    return {"agreement_id": data["id"], "status": "OUT_FOR_SIGNATURE"}
```

**Step 3: Commit**

```bash
git add adobe_sign.py .streamlit/secrets.toml.example
git commit -m "Add Adobe Sign integration module"
```

---

## Task 6: Wire up T&Cs page in `app.py`

**Files:**
- Modify: `app.py`

**Context:** Add "Terms & Conditions" to the sidebar nav. Build the form with conditional service type sections. Integrate draft save/load. Wire up generation, download, and optional Adobe Sign push.

**Step 1: Update DOCUMENT_TYPES dict**

In `app.py`, update the nav dict:

```python
DOCUMENT_TYPES = {
    "Reference Check": "reference_check",
    "Placement Letters": "placement_letters",
    "Terms & Conditions": "terms_conditions",
    "Contractor Agreement": "contractor_agreement",
    "Assignment Confirmation (coming soon)": None,
    "CV Profile (coming soon)": None,
}
```

**Step 2: Add the T&Cs page block**

After the placement letters `elif` block and before the `else`, add the full T&Cs form. Pattern follows the existing placement letters page:

- Import `generators.terms_conditions`
- Import `drafts` module
- Check for existing draft on load → "Resume draft?" prompt
- Form fields with conditional sections per service type
- Auto-save draft on generate click (before generation)
- Generate → download .docx / .pdf
- Delete draft on successful generation
- Optional Adobe Sign push

The form layout:
```
[Client company name]  [Date]

Service Types:
  [x] Permanent / Fixed Term
      Fee: [18]%  On: [Total Salary Package v]  Structure: [Retained v]
      Guarantee: [3 months v]
  [ ] Contractor / Temporary Worker
      Margin: [25]%
  [ ] Retained / Executive Search
      Fee: [25]%  On: [Total Salary Package v]  Structure: [Retained v]

Signature Blocks:
  [ ] Infinitas signature  [ ] Client signature

Output:
  [x] .docx  [ ] .pdf  [ ] Send via Adobe Sign
  [Generate T&Cs]
```

**Step 3: Test in browser**

```bash
cd infinitas-document-hub
streamlit run app.py
```

Test: select T&Cs, fill form, toggle service types on/off, generate, open downloaded .docx.

**Step 4: Commit**

```bash
git add app.py
git commit -m "Add T&Cs generator page to Document Hub"
```

---

## Task 7: Wire up Contractor Agreement page in `app.py`

**Files:**
- Modify: `app.py`

**Context:** Same pattern as T&Cs. Radio button for Sole Trader / Ltd Company. Conditional fields for Ltd Company. Draft persistence. Adobe Sign option.

**Step 1: Add the Contractor Agreement page block**

After T&Cs block. Form layout:

```
Contractor Type: (o) Sole Trader  ( ) Limited Company

--- Assignment Details ---
[Nominated Client]   [Role]
[Commencement Date]  [End Date]
[Hours of Work]      [Contract Rate]
[Notice Period]      [Travel/Expenses]

--- Ltd Company Only (if selected) ---
[Provider Company Name]  [Trading As]
[Registered Address]
[Company No/NZBN]        [Individual Contractor Name]
[IRD Number]             [GST Registered: Yes/No]  [GST Number]
[Bank Account Number]

Output:
  [x] .docx  [ ] .pdf  [ ] Send via Adobe Sign
  [Generate Agreement]
```

**Step 2: Test in browser**

Switch between Sole Trader / Ltd Company, verify fields show/hide. Generate both types, open .docx files.

**Step 3: Commit**

```bash
git add app.py
git commit -m "Add Contractor Agreement page to Document Hub"
```

---

## Task 8: Integration testing and cleanup

**Files:**
- Modify: `requirements.txt` (if any new deps needed — likely none)
- Delete: `build_ltd_company_template.py` (one-time script, no longer needed)
- Delete: test .docx files (`test_contractor.docx`, `test_tcs.docx`)

**Step 1: Full integration test**

In browser, test all flows:
- [ ] T&Cs: all service types on, generate .docx — verify clauses present
- [ ] T&Cs: contractor off, exec off — verify clauses removed, re-numbered
- [ ] T&Cs: perm off, contractor on — verify perm clauses gone
- [ ] T&Cs: signature blocks on — verify appended
- [ ] T&Cs: PDF generation works
- [ ] Contractor: Sole Trader fill — verify Schedule 1 correct
- [ ] Contractor: Ltd Company fill — verify all fields correct
- [ ] Draft: start filling T&Cs, navigate away, come back — draft resumes
- [ ] Draft: complete generation — draft deleted
- [ ] Adobe Sign: verify text tags present in generated PDF (manual check)

**Step 2: Clean up temp files**

```bash
rm build_ltd_company_template.py test_contractor.docx test_tcs.docx
rm -f "Candidate Letter - Jane Smith - Branded v2.docx" "Client Letter - Acme Corp - Branded.docx"
rm -f test_client.docx test_candidate.docx
```

**Step 3: Final commit and push**

```bash
git add -A
git commit -m "Integration testing complete, cleanup temp files"
git push
```

---

## Task 9: Adobe Sign OAuth setup (manual — Tate)

**Not code — configuration steps for Tate:**

1. Go to Adobe Sign admin: https://secure.au1.adobesign.com/account/accountSettingsPage
2. Navigate to **Account** → **Adobe Sign API** → **API Applications**
3. Click **Create** → name it "Document Hub"
4. Configure OAuth:
   - Redirect URI: `https://lion-docuapp.streamlit.app/` (or localhost for testing)
   - Scopes: `agreement_write`, `agreement_send`
5. Note the Client ID and Client Secret
6. Complete the OAuth flow to get a Refresh Token
7. Add all three values to `.streamlit/secrets.toml`

Adobe Sign can be tested after this is done. Everything else works without it.

---

## Execution Order

Tasks 1-2 are prerequisites. Tasks 3-5 are independent generators (can be parallelised). Tasks 6-7 depend on their respective generators. Task 8 is final. Task 9 is manual/async.

```
1 (templates) ─┬─ 3 (contractor gen) ── 7 (contractor page) ──┐
               ├─ 4 (T&Cs gen) ──────── 6 (T&Cs page) ────────┤── 8 (integration)
               ├─ 5 (adobe sign) ──────────────────────────────┘
               └─ 2 (drafts) ──────────────────────────────────┘
```
