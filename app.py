"""Document Hub — branded document generator for the team.

Thin router: handles auth, brand detection, sidebar navigation,
and dispatches to page modules in views/.
"""

import streamlit as st

st.set_page_config(
    page_title="Document Hub",
    page_icon="I",
    layout="wide",
)

# --- Auth Gate ---
from ms_auth import ms_login

if not ms_login():
    st.stop()

# --- Brand Detection ---
from brands import get_brand, get_brand_css

user_email = st.session_state.get("ms_email", "")
brand = get_brand(user_email)
st.markdown(get_brand_css(brand), unsafe_allow_html=True)

# Clean up expired drafts (once per session)
if "_drafts_cleaned" not in st.session_state:
    try:
        from drafts import cleanup_expired
        cleanup_expired()
    except Exception:
        pass
    st.session_state["_drafts_cleaned"] = True

# --- Page State ---
if "current_page" not in st.session_state:
    st.session_state.current_page = "home"


def navigate(page_key: str):
    st.session_state.current_page = page_key


# --- Page Registry ---
PAGE_LABELS = {
    "home": "Home",
    # "chat": "Research Assistant",  # Archived — revisit with proper Next.js frontend
    "shortlist": "Shortlist Generator",
    # "cv_prep": "CV Preparation",
    "reference_check": "Reference Check",
    "placement_letters": "Placement Letters",
    "research_request": "Research Request",
    # "terms_conditions": "Terms & Conditions",
    # "contractor_agreement": "Contractor Agreement",
}

# --- Sidebar ---
st.sidebar.image(brand["logo_url"], width="stretch")
st.sidebar.markdown(
    f'<p style="text-align:center; margin:0.5rem 0 0 0;">'
    f'<strong>{st.session_state.get("ms_user", "User")}</strong></p>',
    unsafe_allow_html=True,
)
st.sidebar.divider()

page_keys = list(PAGE_LABELS.keys())
current_idx = (
    page_keys.index(st.session_state.current_page)
    if st.session_state.current_page in page_keys
    else 0
)

selected_label = st.sidebar.radio(
    "Navigate",
    list(PAGE_LABELS.values()),
    index=current_idx,
    label_visibility="collapsed",
)

# Sync radio selection back to page state
selected_key = page_keys[list(PAGE_LABELS.values()).index(selected_label)]
if selected_key != st.session_state.current_page:
    st.session_state.current_page = selected_key
    st.rerun()

st.sidebar.divider()
if st.sidebar.button("Sign out", width="stretch"):
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

# --- Page Routing ---
page = st.session_state.current_page

if page == "home":
    from views.home import render
    render(navigate)

elif page == "shortlist":
    from views.shortlist import render
    render()

elif page == "cv_prep":
    from views.cv_prep import render
    render()

elif page == "reference_check":
    from views.reference_check import render
    render()

elif page == "placement_letters":
    from views.placement_letters import render
    render()

elif page == "research_request":
    from views.research_request import render
    render()

elif page == "terms_conditions":
    from views.terms_conditions import render
    render(user_email)

elif page == "contractor_agreement":
    from views.contractor_agreement import render
    render(user_email)

else:
    st.info("This document type is coming soon.")
