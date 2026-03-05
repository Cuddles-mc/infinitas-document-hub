"""Microsoft OAuth delegated auth for Streamlit + Graph API PDF conversion."""

import base64
import io
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
    base = _drive_base_url()

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
    folder_id: str | None = None,
    drive_id: str | None = None,
    folder_path: str | None = None,
) -> tuple[str | None, str | None]:
    """Save a file to OneDrive.

    Uses folder_id + drive_id if available (most reliable).
    Falls back to folder_path if no ID provided.

    Returns:
        Tuple of (web_url, error_message). One will be None.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return None, "Not authenticated. Sign out and back in."

    headers = {"Authorization": f"Bearer {token}"}

    if folder_id and drive_id:
        upload_url = f"https://graph.microsoft.com/v1.0/drives/{drive_id}/items/{folder_id}:/{filename}:/content"
    elif folder_path:
        base = _drive_base_url()
        safe_path = folder_path.replace("\\", "/")
        upload_url = f"{base}/root:/{safe_path}/{filename}:/content"
    else:
        return None, "No folder specified."

    resp = requests.put(
        upload_url,
        headers={**headers, "Content-Type": "application/octet-stream"},
        data=file_bytes,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        return resp.json().get("webUrl"), None

    # Parse error
    try:
        err = resp.json().get("error", {})
        msg = f"{resp.status_code}: {err.get('code', '')} — {err.get('message', resp.text[:200])}"
    except Exception:
        msg = f"{resp.status_code}: {resp.text[:200]}"
    return None, msg


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


CANDIDATES_FOLDER = "Day to Day/Candidates"


def _find_drive_id() -> str | None:
    """Find the drive ID for the Infinitas Talent shared drive.

    Searches user's available drives for one containing 'Day to Day'.
    Falls back to personal drive if not found.
    """
    if "ms_drive_id" in st.session_state:
        return st.session_state.ms_drive_id

    token = st.session_state.get("ms_access_token")
    if not token:
        return None

    headers = {"Authorization": f"Bearer {token}"}

    # Try personal OneDrive first
    resp = requests.get(
        f"https://graph.microsoft.com/v1.0/me/drive/root:/{CANDIDATES_FOLDER}:/",
        headers=headers, timeout=15,
    )
    if resp.status_code == 200:
        drive_id = resp.json().get("parentReference", {}).get("driveId")
        if drive_id:
            st.session_state.ms_drive_id = drive_id
            return drive_id

    # Search across all drives the user has access to
    resp = requests.get(
        "https://graph.microsoft.com/v1.0/me/drives?$select=id,name",
        headers=headers, timeout=15,
    )
    if resp.status_code == 200:
        for drive in resp.json().get("value", []):
            drive_id = drive["id"]
            check = requests.get(
                f"https://graph.microsoft.com/v1.0/drives/{drive_id}/root:/{CANDIDATES_FOLDER}:/",
                headers=headers, timeout=15,
            )
            if check.status_code == 200:
                st.session_state.ms_drive_id = drive_id
                return drive_id

    return None


def _drive_base_url() -> str:
    """Get the Graph API base URL for the correct drive."""
    drive_id = _find_drive_id()
    if drive_id:
        return f"https://graph.microsoft.com/v1.0/drives/{drive_id}"
    return "https://graph.microsoft.com/v1.0/me/drive"


def search_candidate_folder(candidate_name: str) -> list[dict]:
    """Search for a candidate's folder in Day to Day/Candidates/.

    Returns list of dicts with 'path', 'id', and 'driveId' keys.
    """
    token = st.session_state.get("ms_access_token")
    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}

    # Try each possible drive endpoint
    endpoints = [
        _drive_base_url(),
        "https://graph.microsoft.com/v1.0/me/drive",
    ]

    # Also try all user drives
    drives_resp = requests.get(
        "https://graph.microsoft.com/v1.0/me/drives?$select=id",
        headers=headers, timeout=15,
    )
    if drives_resp.status_code == 200:
        for d in drives_resp.json().get("value", []):
            endpoints.append(f"https://graph.microsoft.com/v1.0/drives/{d['id']}")

    # Deduplicate
    seen = set()
    unique_endpoints = []
    for ep in endpoints:
        if ep not in seen:
            seen.add(ep)
            unique_endpoints.append(ep)

    name_lower = candidate_name.lower()
    matches = []

    for base in unique_endpoints:
        url = (
            f"{base}/root:/{CANDIDATES_FOLDER}:/children"
            f"?$filter=folder ne null&$select=name,id,parentReference&$top=200"
        )
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            continue

        for item in resp.json().get("value", []):
            folder_name = item["name"]
            if name_lower in folder_name.lower():
                drive_id = item.get("parentReference", {}).get("driveId", "")
                matches.append({
                    "path": f"{CANDIDATES_FOLDER}/{folder_name}",
                    "id": item["id"],
                    "driveId": drive_id,
                })
        if matches:
            break  # Found on this drive, no need to check others

    return matches


def build_outlook_compose_url(
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Build an Outlook Web compose URL with pre-filled fields.

    Opens a new email in Outlook Web with signature automatically included.
    """
    from urllib.parse import quote
    return (
        f"https://outlook.office365.com/mail/deeplink/compose"
        f"?to={quote(to_email)}"
        f"&subject={quote(subject)}"
        f"&body={quote(body)}"
    )
