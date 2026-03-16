"""Research Request page — submit and track research requests for the team."""

import json
from datetime import datetime, timezone
from urllib.parse import quote
import requests as http_requests
import streamlit as st
from ui import page_header, form_section


# --- Supabase helpers (follows drafts.py pattern) ---

def _headers():
    return {
        "apikey": st.secrets["SUPABASE_SERVICE_KEY"],
        "Authorization": f"Bearer {st.secrets['SUPABASE_SERVICE_KEY']}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _base_url():
    return f"{st.secrets['SUPABASE_URL']}/rest/v1/wiki_requests"


def _insert_request(data: dict) -> bool:
    """Insert a wiki_request row. Returns True on success."""
    try:
        resp = http_requests.post(
            _base_url(),
            headers=_headers(),
            json=data,
            timeout=10,
        )
        return resp.status_code in (200, 201)
    except Exception:
        return False


def _fetch_requests() -> list[dict]:
    """Fetch all wiki_requests, most recent first."""
    try:
        resp = http_requests.get(
            _base_url(),
            headers=_headers(),
            params={
                "select": "id,request_type,subject,context,priority,status,requested_by,created_at,completed_wiki_slug",
                "order": "created_at.desc",
                "limit": "50",
            },
            timeout=10,
        )
        return resp.json() if resp.status_code == 200 else []
    except Exception:
        return []


def _cancel_request(request_id: int) -> bool:
    """Set a request status to cancelled."""
    try:
        resp = http_requests.patch(
            _base_url(),
            headers={**_headers(), "Prefer": "return=minimal"},
            params={"id": f"eq.{request_id}"},
            json={"status": "cancelled"},
            timeout=10,
        )
        return resp.status_code in (200, 204)
    except Exception:
        return False


# --- Type-specific form fields ---

REQUEST_TYPES = {
    "Person": "person",
    "Company": "company",
    "Sector": "sector",
    "Intel Signal": "intel",
    "BD Dossier": "dossier",
    "BD Playbook": "playbook",
}

SIGNAL_TYPES = [
    "Competitor Placement",
    "Competitor Advertising",
    "Competitor Win",
    "Leadership Change",
    "Departure",
    "New Role Created",
    "Financial Results",
    "Salary Data",
    "Sector Analysis",
    "BD Research",
    "Other",
]

REGIONS = [
    "auckland",
    "wellington",
    "christchurch",
    "bay-of-plenty",
    "hawkes-bay",
    "waikato",
    "other-nz",
    "nz-wide",
    "australia",
    "offshore",
]

# --- Status badge styling ---

STATUS_COLOURS = {
    "pending": ("#6B7280", "#F3F4F6"),
    "in_progress": ("#1D4ED8", "#DBEAFE"),
    "done": ("#059669", "#D1FAE5"),
    "error": ("#DC2626", "#FEE2E2"),
    "cancelled": ("#9CA3AF", "#F9FAFB"),
}


def _status_badge(status: str) -> str:
    text_col, bg_col = STATUS_COLOURS.get(status, ("#6B7280", "#F3F4F6"))
    label = status.replace("_", " ").title()
    return (
        f'<span style="background:{bg_col}; color:{text_col}; '
        f'padding:2px 10px; border-radius:12px; font-size:0.8rem; '
        f'font-weight:500;">{label}</span>'
    )


def _obsidian_link(slug: str) -> str:
    if not slug:
        return ""
    encoded = quote(slug, safe="")
    uri = f"obsidian://open?vault=infinitas-research&file={encoded}"
    return f'<a href="{uri}" target="_blank">Open in Obsidian</a>'


# --- Main render ---

def render():
    page_header("Research Request", "Submit research requests for the team")

    _render_form()
    st.divider()
    _render_status_table()


def _render_form():
    form_section("New Request")

    type_label = st.radio(
        "Research type",
        list(REQUEST_TYPES.keys()),
        horizontal=True,
    )
    request_type = REQUEST_TYPES[type_label]

    # Dynamic fields per type
    context_data = {}

    if request_type == "person":
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Person name *")
            company = st.text_input("Current company")
        with col2:
            linkedin = st.text_input("LinkedIn URL")
            context_notes = st.text_input("Context (optional)")
        if company:
            context_data["company"] = company
        if linkedin:
            context_data["linkedin_url"] = linkedin
        if context_notes:
            context_data["notes"] = context_notes

    elif request_type == "company":
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Company name *")
            website = st.text_input("Website URL")
        with col2:
            linkedin = st.text_input("LinkedIn URL")
            context_notes = st.text_input("Context (optional)")
        if website:
            context_data["website"] = website
        if linkedin:
            context_data["linkedin_url"] = linkedin
        if context_notes:
            context_data["notes"] = context_notes

    elif request_type == "sector":
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Sector name *")
        with col2:
            region = st.selectbox("Region", [""] + REGIONS)
        context_notes = st.text_input("Context (optional)")
        if region:
            context_data["region"] = region
        if context_notes:
            context_data["notes"] = context_notes

    elif request_type == "intel":
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Signal subject *")
            signal_type = st.selectbox("Signal type", [""] + SIGNAL_TYPES)
        with col2:
            companies_affected = st.text_input("Companies affected")
            context_notes = st.text_input("Context (optional)")
        if signal_type:
            context_data["signal_type"] = signal_type
        if companies_affected:
            context_data["companies_affected"] = companies_affected
        if context_notes:
            context_data["notes"] = context_notes

    elif request_type == "dossier":
        col1, col2 = st.columns(2)
        with col1:
            subject = st.text_input("Company name *")
        with col2:
            contact_name = st.text_input("Contact name (optional)")
        context_notes = st.text_input("Context (optional)")
        if contact_name:
            context_data["contact_name"] = contact_name
        if context_notes:
            context_data["notes"] = context_notes

    elif request_type == "playbook":
        subject = st.text_input("Sector / niche name *")
        context_notes = st.text_input("Context (optional)")
        if context_notes:
            context_data["notes"] = context_notes

    # Priority
    priority = st.radio("Priority", ["Low", "Normal", "Urgent"], index=1, horizontal=True)

    # Submit
    st.markdown("")
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        submit = st.button("Submit Request", type="primary", use_container_width=True)

    if submit:
        if not subject or not subject.strip():
            st.error("Please enter a name / subject.")
            return

        user_name = st.session_state.get("ms_user", "Unknown")
        user_email = st.session_state.get("ms_email", "")

        row = {
            "request_type": request_type,
            "subject": subject.strip(),
            "context": json.dumps(context_data) if context_data else None,
            "priority": priority.lower(),
            "requested_by": user_email or user_name,
            "status": "pending",
        }

        if _insert_request(row):
            st.success(f"Research request submitted: **{subject}** ({type_label})")
            st.rerun()
        else:
            st.error("Failed to submit request. Please try again.")


def _render_status_table():
    form_section("Request Queue")

    col_title, col_refresh = st.columns([3, 1])
    with col_refresh:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    rows = _fetch_requests()

    if not rows:
        st.info("No research requests yet.")
        return

    # Table header
    st.markdown(
        '<div style="display:grid; grid-template-columns: 0.8fr 2fr 0.7fr 0.8fr 1.2fr 0.8fr 1fr; '
        'gap:8px; padding:8px 12px; font-size:0.8rem; font-weight:600; color:#6B7280; '
        'border-bottom:2px solid #E5E7EB; text-transform:uppercase; letter-spacing:0.04em;">'
        '<div>Type</div><div>Subject</div><div>Priority</div><div>Status</div>'
        '<div>Requested By</div><div>Date</div><div>Link</div></div>',
        unsafe_allow_html=True,
    )

    for row in rows:
        status = row.get("status", "pending")
        created = row.get("created_at", "")[:10]
        slug = row.get("completed_wiki_slug", "")
        requested_by = row.get("requested_by", "")
        # Show display name portion of email if it's an email
        if "@" in requested_by:
            display_name = requested_by.split("@")[0].replace(".", " ").title()
        else:
            display_name = requested_by

        priority_label = (row.get("priority", "normal") or "normal").title()
        type_label = (row.get("request_type", "") or "").replace("_", " ").title()

        link_html = _obsidian_link(slug) if status == "done" and slug else ""

        st.markdown(
            f'<div style="display:grid; grid-template-columns: 0.8fr 2fr 0.7fr 0.8fr 1.2fr 0.8fr 1fr; '
            f'gap:8px; padding:10px 12px; font-size:0.85rem; border-bottom:1px solid #F3F4F6; '
            f'align-items:center;">'
            f'<div>{type_label}</div>'
            f'<div style="font-weight:500;">{row.get("subject", "")}</div>'
            f'<div>{priority_label}</div>'
            f'<div>{_status_badge(status)}</div>'
            f'<div style="color:#6B7280;">{display_name}</div>'
            f'<div style="color:#9CA3AF;">{created}</div>'
            f'<div>{link_html}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # Cancel button for pending requests
        if status == "pending":
            cancel_col, _ = st.columns([1, 6])
            with cancel_col:
                if st.button("Cancel", key=f"cancel_{row['id']}", type="secondary"):
                    if _cancel_request(row["id"]):
                        st.rerun()
