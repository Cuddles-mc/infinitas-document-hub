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
            # Try multiple claim fields for email
            email = (
                claims.get("preferred_username")
                or claims.get("email")
                or claims.get("upn")
                or ""
            )
            # Guest users may have UPN like user_domain#EXT#@tenant.onmicrosoft.com
            # Always fetch from Graph API /me for the real mail address
            try:
                me = requests.get(
                    "https://graph.microsoft.com/v1.0/me?$select=mail,userPrincipalName,otherMails",
                    headers={"Authorization": f"Bearer {result['access_token']}"},
                    timeout=10,
                ).json()
                graph_email = me.get("mail") or ""
                graph_upn = me.get("userPrincipalName") or ""
                graph_other = (me.get("otherMails") or [None])[0] or ""
                if graph_email and "@" in graph_email:
                    email = graph_email
                elif not email or "#EXT#" in email or "onmicrosoft.com" in email:
                    email = graph_email or graph_other or graph_upn or email
            except Exception:
                pass
            st.session_state.ms_email = email
            st.query_params.clear()
            st.rerun()
        else:
            error = result.get("error_description", result.get("error", "Unknown error"))
            st.error(f"Login failed: {error}")
            return False

    # --- Login page ---
    auth_url = app.get_authorization_request_url(
        scopes=SCOPES,
        redirect_uri=st.secrets["MS_REDIRECT_URI"],
    )

    col1, col2, col3 = st.columns([1, 1.5, 1])
    with col2:
        st.markdown("")
        st.markdown("")
        with st.container(border=True):
            st.markdown(
                '<div style="text-align: center; padding: 1.5rem 0 0.5rem 0;">',
                unsafe_allow_html=True,
            )
            st.image(
                "https://infinitas.co.nz/wp-content/uploads/2024/11/Infinitas-Logo-HRZ-2.svg",
                use_container_width=True,
            )
            st.markdown("</div>", unsafe_allow_html=True)
            st.markdown("")
            st.markdown(
                '<p style="text-align: center; color: #6B7280; font-size: 1rem; '
                'margin-bottom: 1.5rem;">Document Hub</p>',
                unsafe_allow_html=True,
            )
            st.link_button(
                "Sign in with Microsoft",
                auth_url,
                use_container_width=True,
            )
            st.markdown("")
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
    """Build an Outlook Web compose URL with pre-filled fields (no attachments)."""
    from urllib.parse import quote
    return (
        f"https://outlook.office365.com/mail/deeplink/compose"
        f"?to={quote(to_email)}"
        f"&subject={quote(subject)}"
        f"&body={quote(body)}"
    )



