"""Draft persistence for Document Hub via Supabase.
Auto-saves form state so users can resume later.
Invisible to users — no database references in UI."""

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
    """Load a draft if one exists. Returns dict with form_data and updated_at, or None."""
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
        from datetime import timedelta
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        requests.delete(
            _base_url(),
            headers=_headers(),
            params={"updated_at": f"lt.{cutoff}"},
            timeout=5,
        )
    except Exception:
        pass
