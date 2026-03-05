"""Microsoft OAuth delegated auth for Streamlit + Graph API helpers."""

import msal
import requests
import streamlit as st


AUTHORITY = f"https://login.microsoftonline.com/{st.secrets['MS_TENANT_ID']}"
SCOPES = ["Files.ReadWrite", "User.Read"]


def _get_msal_app():
    """Return a confidential MSAL client."""
    return msal.ConfidentialClientApplication(
        st.secrets["MS_CLIENT_ID"],
        authority=AUTHORITY,
        client_credential=st.secrets["MS_CLIENT_SECRET"],
    )


def ms_login():
    """Handle Microsoft OAuth login flow. Returns True if authenticated."""
    if st.session_state.get("ms_authenticated"):
        return True

    app = _get_msal_app()

    # Check if we have an auth code in the URL (callback from Microsoft)
    params = st.query_params
    code = params.get("code")

    if code:
        result = app.acquire_token_by_authorization_code(
            code,
            scopes=SCOPES,
            redirect_uri=st.secrets["MS_REDIRECT_URI"],
        )
        if "access_token" in result:
            claims = result.get("id_token_claims", {})
            st.session_state.ms_authenticated = True
            st.session_state.ms_access_token = result["access_token"]
            st.session_state.ms_user = claims.get("name", "User")
            st.session_state.ms_email = claims.get("preferred_username", "")
            st.query_params.clear()
            st.rerun()
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            st.error(f"Login failed: {error}")
            return False

    # Show login page
    auth_url = app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=st.secrets["MS_REDIRECT_URI"],
    )

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("###")
        st.title("Document Hub")
        st.caption("Branded document generation for the team")
        st.markdown("###")
        st.link_button(
            "Sign in with Microsoft",
            auth_url,
            use_container_width=True,
        )
    return False


def convert_docx_to_pdf_graph(docx_bytes: bytes, filename: str = "document.docx") -> bytes | None:
    """Convert .docx to PDF using Microsoft Graph API.

    Uploads to user's OneDrive temp folder, requests PDF format, downloads, deletes.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    base = "https://graph.microsoft.com/v1.0/me/drive"

    try:
        # Upload to temp folder
        upload_url = f"{base}/root:/DocumentHub-temp/{filename}:/content"
        resp = requests.put(
            upload_url,
            headers={**headers, "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"},
            data=docx_bytes,
            timeout=30,
        )
        if resp.status_code not in (200, 201):
            return None

        item_id = resp.json()["id"]

        # Download as PDF
        pdf_url = f"{base}/items/{item_id}/content?format=pdf"
        pdf_resp = requests.get(pdf_url, headers=headers, timeout=30)
        if pdf_resp.status_code != 200:
            requests.delete(f"{base}/items/{item_id}", headers=headers, timeout=10)
            return None

        pdf_bytes = pdf_resp.content

        # Delete temp file
        requests.delete(f"{base}/items/{item_id}", headers=headers, timeout=10)

        return pdf_bytes

    except Exception:
        return None


def build_outlook_compose_url(to_email: str, subject: str, body: str) -> str:
    """Build an Outlook Web compose URL with pre-filled fields."""
    from urllib.parse import quote
    return (
        f"https://outlook.office365.com/mail/deeplink/compose"
        f"?to={quote(to_email)}"
        f"&subject={quote(subject)}"
        f"&body={quote(body)}"
    )
