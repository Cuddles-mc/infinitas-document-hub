"""Microsoft OAuth delegated auth for Streamlit + Graph API PDF conversion."""

import base64
import io
import msal
import requests
import streamlit as st


AUTHORITY = f"https://login.microsoftonline.com/{st.secrets['MS_TENANT_ID']}"
SCOPES = ["Files.ReadWrite", "User.Read", "Mail.Send"]


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
        # Exchange code for tokens
        result = app.acquire_token_by_authorization_code(
            code,
            scopes=SCOPES,
            redirect_uri=st.secrets["MS_REDIRECT_URI"],
        )
        if "access_token" in result:
            st.session_state.ms_authenticated = True
            st.session_state.ms_access_token = result["access_token"]
            st.session_state.ms_user = result.get("id_token_claims", {}).get("name", "User")
            # Clear the code from URL
            st.query_params.clear()
            st.rerun()
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            st.error(f"Login failed: {error}")
            return False

    # Show login button
    auth_url = app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=st.secrets["MS_REDIRECT_URI"],
    )
    st.title("Infinitas Document Hub")
    st.link_button("Sign in with Microsoft", auth_url)
    return False


def convert_docx_to_pdf_graph(docx_bytes: bytes, filename: str = "document.docx") -> bytes | None:
    """Convert .docx to PDF using Microsoft Graph API (delegated).

    Uploads to user's OneDrive, requests PDF format, downloads, then deletes.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    base = "https://graph.microsoft.com/v1.0/me/drive"

    try:
        # Upload to a temp folder in OneDrive
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
            # Clean up even on failure
            requests.delete(f"{base}/items/{item_id}", headers=headers, timeout=10)
            return None

        pdf_bytes = pdf_resp.content

        # Delete temp file
        requests.delete(f"{base}/items/{item_id}", headers=headers, timeout=10)

        return pdf_bytes

    except Exception:
        return None


def save_to_onedrive(
    file_bytes: bytes,
    filename: str,
    folder_path: str,
) -> str | None:
    """Save a file to OneDrive under the given folder path.

    Args:
        file_bytes: The file content.
        filename: Name for the file.
        folder_path: OneDrive folder path (e.g. "Placements/John Smith").

    Returns:
        The web URL of the saved file, or None on failure.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}
    safe_path = folder_path.replace("\\", "/")
    upload_url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{safe_path}/{filename}:/content"

    resp = requests.put(
        upload_url,
        headers={**headers, "Content-Type": "application/octet-stream"},
        data=file_bytes,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        return resp.json().get("webUrl")
    return None


def send_email(
    to_email: str,
    subject: str,
    body_html: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> bool:
    """Send an email via Microsoft Graph API as the logged-in user.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        body_html: HTML body content.
        attachments: List of (filename, file_bytes) tuples.

    Returns:
        True if sent successfully.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    message = {
        "message": {
            "subject": subject,
            "body": {
                "contentType": "HTML",
                "content": body_html,
            },
            "toRecipients": [
                {"emailAddress": {"address": to_email}}
            ],
        }
    }

    if attachments:
        message["message"]["attachments"] = []
        for filename, file_bytes in attachments:
            message["message"]["attachments"].append({
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": filename,
                "contentBytes": base64.b64encode(file_bytes).decode("utf-8"),
            })

    resp = requests.post(
        "https://graph.microsoft.com/v1.0/me/sendMail",
        headers=headers,
        json=message,
        timeout=30,
    )
    return resp.status_code == 202
