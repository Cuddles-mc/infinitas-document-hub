# Document Hub Phase 2 — Design

**Date:** 2026-03-06
**Status:** Approved

## Scope

Two new document generators, draft persistence, and Adobe Sign integration.

**Not in scope:** Multi-brand (Luminous/Origin), Proposal Generator (PowerPoint), SharePoint integration, Mail.ReadWrite (no admin consent available).

---

## 1. T&Cs Generator

### User Flow
1. Select "Terms & Conditions" from sidebar nav
2. Fill form fields (or resume a saved draft)
3. Toggle service types on/off — per-type fee fields appear/disappear
4. Tick signature block options
5. Click Generate
6. Download .docx / .pdf, optionally push to Adobe Sign

### Form Fields

| Field | Type | Default |
|---|---|---|
| Client company name | Text input | — |
| Date | Date picker | Today |
| **Service types (toggle on/off):** | | |
| Permanent / Fixed Term | Checkbox | on |
| Contractor / Temporary Worker | Checkbox | off |
| Retained / Executive Search | Checkbox | off |
| **Per enabled service type:** | | |
| Fee % | Number input | 18% (perm/fixed) / 25% (exec/contract) |
| Calculated on | Dropdown: Base Salary / Total Salary Package | Total Salary Package |
| Fee structure | Dropdown: Retained (thirds) / Contingent / Fixed Fee | Retained |
| Fixed fee amount (if Fixed Fee selected) | Text input | — |
| Guarantee period | Dropdown: 3 / 6 / 12 months | 3 months |
| **Contracting-specific:** | | |
| Margin % | Number input | 25% |
| **Signature blocks:** | | |
| Include Infinitas signature | Checkbox | off |
| Include Client signature | Checkbox | off |
| **Output:** | | |
| .docx | Checkbox | on |
| .pdf | Checkbox | off |
| Send via Adobe Sign | Checkbox | off |

### Generation Logic

**Template:** `Infinitas Talent - Terms and Conditions.docx` (master copy)

1. **Fill client name** — replace `[PARTY 2]` in Table 1
2. **Update Guarantee Period definition** — replace "three (3) calendar months" with selected period
3. **Remove toggled-off service type sections:**
   - Contractor/Temp off → remove clauses 6 (Fees — Contractor/Temp), 7 (Further Contracting fees), related Client Obligations sub-clauses, contracting entries from Schedule 1
   - Exec Search off → remove clause 8 (Fees — Retained/Exec Search), its Schedule 1 entry
   - Perm/Fixed Term off → remove clauses 4 (Placement Fee), 5 (Liability to Pay), their Schedule 1 entries
4. **Re-number clauses** — build old→new clause number mapping, update all 10 cross-references in a single pass:
   - [64] clause 5 and 6
   - [66] clause 10
   - [74] clause 3.1
   - [96] clause 17
   - [118] clause 4
   - [153] clause 7.1
   - [155] clause 7.1
   - [194] clause 10.1
   - [291] clause 5
   - [299] clause 17.3
5. **Rewrite Schedule 1** — regenerate fee schedule text per enabled service type with custom percentages, salary basis, fee structure
6. **Optionally append signature block** — two-row table (Infinitas / Client) with name, date, signature lines. Embed Adobe Sign text tags if enabled.

### Current Clause Structure (for removal mapping)

| # | Section | Removable? |
|---|---|---|
| 1 | Definitions | Never (but Guarantee Period definition is editable) |
| 2 | Term | Never |
| 3 | Right of Renewal | Never |
| 4 | Placement Fee (Perm/Fixed Term) | Yes — if Perm/Fixed Term off |
| 5 | Liability to Pay | Yes — if Perm/Fixed Term off |
| 6 | Fees — Contractor/Temp | Yes — if Contractor/Temp off |
| 7 | Further Contracting Fees | Yes — if Contractor/Temp off |
| 8 | Fees — Retained/Exec Search | Yes — if Exec Search off |
| 9 | Expenses | Never |
| 10 | Placement Guarantee | Never |
| 11 | Client Obligations | Never (but some sub-clauses reference temp workers) |
| 12 | Infinitas Obligations | Never |
| 13 | Limitation of Liability | Never |
| 14 | GST | Never |
| 15 | Anti-Corruption | Never |
| 16 | Confidentiality & Privacy | Never |
| 17 | Termination | Never |
| 18 | Consequences of Termination | Never |
| 19 | General Provisions | Never |
| 20 | Schedule 1: Fee Schedule | Always present, content varies |

---

## 2. Contractor Agreement Generator

### User Flow
1. Select "Contractor Agreement" from sidebar nav
2. Pick contractor type: Sole Trader / Limited Company
3. Fill Schedule 1 fields (Ltd Company shows extra fields)
4. Click Generate
5. Download .docx / .pdf, optionally push to Adobe Sign

### Form Fields

| Field | Type | Both types? |
|---|---|---|
| Contractor type | Radio: Sole Trader / Limited Company | — |
| **Schedule 1 — Assignment Details:** | | |
| Nominated Client | Text input | Yes |
| Role | Text input | Yes |
| Commencement Date | Date picker | Yes |
| End Date | Date picker | Yes |
| Hours of Work | Text input | Yes |
| Contract Rate | Text input | Yes |
| Notice Period | Text input | Yes |
| Other/Travel Expenses | Text input (default: "Upon authorisation by the Nominated Client") | Yes |
| **Ltd Company only:** | | |
| Provider company name | Text input | Ltd only |
| Trading as (if applicable) | Text input | Ltd only |
| Registered address | Text area | Ltd only |
| Company No. / NZBN | Text input | Ltd only |
| Name of Individual Contractor | Text input | Ltd only |
| IRD Number | Text input | Ltd only |
| GST Registered | Radio: Yes / No | Ltd only |
| GST Number (if registered) | Text input | Ltd only |
| Nominated Bank Account Number | Text input | Ltd only |
| **Output:** | | |
| .docx | Checkbox | on |
| .pdf | Checkbox | off |
| Send via Adobe Sign | Checkbox | off |

### Generation Logic

**Templates:**
- Sole Trader: `Contractor Agreement Sole Trader.docx`
- Ltd Company: `Contractor Agreement Limited Company.docx` (created 2026-03-06)

Simple form fill — no toggleable sections. Replace Schedule 1 placeholder fields with form values. Both templates always include two signature blocks.

### Templates Location
```
Day to Day/Templates/Document Templates/Placement and Contract Templates/
  Assignment Confirmations[Contracts]/Contractor agreements 2025 (NEW)/
    New Infinitas Documents/
      Contractor Agreement Sole Trader.docx
      Contractor Agreement Limited Company.docx
```

---

## 3. Draft Persistence

### Architecture
- **Storage:** Supabase table `doc_hub_drafts` (private — invisible to app users)
- **Credentials:** Supabase URL + service key in Streamlit `secrets.toml`

### Schema
```sql
CREATE TABLE doc_hub_drafts (
    id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
    user_email TEXT NOT NULL,
    doc_type TEXT NOT NULL,  -- 'terms_conditions', 'contractor_agreement', etc.
    form_data JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (user_email, doc_type)
);
```

### Behaviour
- **Auto-save:** On every form field change, upsert the draft (debounced)
- **Auto-load:** On page load, check for existing draft matching `user_email` + `doc_type`
- **Resume prompt:** If draft exists, show "Resume draft from [date]?" with Resume / Start Fresh buttons
- **Delete on generate:** After successful document generation, delete the draft
- **Expiry:** Cron or app-side check — delete drafts older than 30 days
- **User experience:** Seamless. No mention of database, storage, or technical details. Drafts just persist.

---

## 4. Adobe Sign Integration

### Auth
- Plan: Adobe Acrobat Sign Teams (confirmed)
- Auth method: OAuth 2.0 (Adobe Sign API v6)
- Credentials: stored in Streamlit `secrets.toml`

### Flow
1. Generate document as .docx
2. Convert to PDF (via Graph API, existing flow)
3. Embed Adobe Sign text tags in signature fields during generation:
   - `{{Sig_es_:signer1:signature}}` — Infinitas signatory
   - `{{Sig_es_:signer2:signature}}` — Client/Contractor signatory
   - `{{Dte_es_:signer1:date}}`, `{{Dte_es_:signer2:date}}` — date fields
4. POST PDF to Adobe Sign API as a transient document
5. Create agreement with signer email(s)
6. Adobe Sign sends email to signers with pre-mapped fields
7. Show confirmation in UI with link to track signing status

### Shared Module
`adobe_sign.py` — used by both T&Cs and Contractor Agreement generators. Functions:
- `upload_document(pdf_bytes)` → transient document ID
- `send_for_signature(doc_id, signers, agreement_name)` → agreement ID + status URL

---

## 5. Existing Features Updated

### Sidebar Navigation (updated)
- Reference Check
- Placement Letters
- Terms & Conditions ← new
- Contractor Agreement ← new
- Assignment Confirmation (coming soon)
- CV Profile (coming soon)

---

## Prerequisites

| Item | Owner | Status |
|---|---|---|
| Adobe Sign API credentials (OAuth app in Adobe admin) | Tate | To do |
| Copy template .docx files to Document Hub repo `/templates/` | Build script | To do |

### Explicitly Not Available
- No Azure admin consent (no Mail.ReadWrite, no Files.ReadWrite.All)
- No SharePoint integration
- Email sending via Outlook compose deep links only (no attachments)

---

## File Structure (new/modified)

```
infinitas-document-hub/
  generators/
    terms_conditions.py     ← new
    contractor_agreement.py ← new
  templates/
    terms-conditions.docx                   ← copy from master
    contractor-agreement-sole-trader.docx   ← copy from master
    contractor-agreement-ltd-company.docx   ← copy from master
  adobe_sign.py             ← new
  drafts.py                 ← new (Supabase draft persistence)
  app.py                    ← updated (new nav items, draft integration)
  brands.py                 ← unchanged
  ms_auth.py                ← unchanged
```
