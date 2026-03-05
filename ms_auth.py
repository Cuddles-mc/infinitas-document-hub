"""Microsoft OAuth delegated auth for Streamlit + Graph API PDF conversion."""

import base64
import io
import msal
import requests
import streamlit as st


AUTHORITY = f"https://login.microsoftonline.com/{st.secrets['MS_TENANT_ID']}"
SCOPES = ["Files.ReadWrite", "User.Read", "Mail.ReadWrite"]


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


def list_onedrive_folders(path: str = "") -> list[dict] | None:
    """List folders in a OneDrive path.

    Returns list of dicts with 'name' and 'path' keys, or None on failure.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}

    if path:
        safe_path = path.replace("\\", "/")
        url = f"https://graph.microsoft.com/v1.0/me/drive/root:/{safe_path}:/children?$filter=folder ne null&$select=name,parentReference&$top=100"
    else:
        url = "https://graph.microsoft.com/v1.0/me/drive/root/children?$filter=folder ne null&$select=name,parentReference&$top=100"

    resp = requests.get(url, headers=headers, timeout=15)
    if resp.status_code != 200:
        return None

    items = resp.json().get("value", [])
    folders = []
    for item in items:
        parent_path = item.get("parentReference", {}).get("path", "")
        # parentReference.path looks like "/drive/root:/Some/Path"
        if "root:" in parent_path:
            parent = parent_path.split("root:")[-1].lstrip("/")
            folder_path = f"{parent}/{item['name']}" if parent else item["name"]
        else:
            folder_path = item["name"]
        folders.append({"name": item["name"], "path": folder_path})

    return sorted(folders, key=lambda f: f["name"].lower())


def create_onedrive_folder(path: str) -> bool:
    """Create a folder in OneDrive. Creates parent folders automatically."""
    token = st.session_state.get("ms_access_token")
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    parts = path.replace("\\", "/").split("/")
    current = ""
    for part in parts:
        parent_url = (
            f"https://graph.microsoft.com/v1.0/me/drive/root:/{current}:/children"
            if current
            else "https://graph.microsoft.com/v1.0/me/drive/root/children"
        )
        resp = requests.post(
            parent_url,
            headers=headers,
            json={"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "fail"},
            timeout=15,
        )
        # 201 = created, 409 = already exists — both fine
        current = f"{current}/{part}" if current else part

    return True


def create_draft(
    to_email: str,
    subject: str,
    body_html: str,
    attachments: list[tuple[str, bytes]] | None = None,
) -> str | None:
    """Create an email draft in Outlook via Graph API, return the web link to open it.

    The draft includes attachments and will pick up the user's Outlook signature
    when opened in Outlook.

    Returns:
        Outlook Web URL to open the draft, or None on failure.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return None

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    message = {
        "subject": subject,
        "body": {
            "contentType": "HTML",
            "content": body_html,
        },
        "toRecipients": [
            {"emailAddress": {"address": to_email}}
        ],
    }

    # Create the draft
    resp = requests.post(
        "https://graph.microsoft.com/v1.0/me/messages",
        headers=headers,
        json=message,
        timeout=30,
    )
    if resp.status_code != 201:
        return None

    draft = resp.json()
    draft_id = draft["id"]
    web_link = draft.get("webLink")

    # Add attachments to the draft
    if attachments:
        for filename, file_bytes in attachments:
            attachment = {
                "@odata.type": "#microsoft.graph.fileAttachment",
                "name": filename,
                "contentBytes": base64.b64encode(file_bytes).decode("utf-8"),
            }
            requests.post(
                f"https://graph.microsoft.com/v1.0/me/messages/{draft_id}/attachments",
                headers=headers,
                json=attachment,
                timeout=30,
            )

    return web_link
