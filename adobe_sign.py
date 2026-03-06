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
