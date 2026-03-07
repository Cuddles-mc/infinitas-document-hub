"""Home page — document type gallery inspired by PandaDoc template picker."""

import streamlit as st


DOCUMENT_CARDS = [
    {
        "key": "reference_check",
        "title": "Reference Check",
        "description": "AI-powered reference check from a call transcript. Extracts answers to 26 standard questions, generates branded .docx.",
        "badge": "AI",
        "badge_colour": "#7C3AED",
    },
    {
        "key": "placement_letters",
        "title": "Placement Letters",
        "description": "Client and candidate confirmation letters. Upload a Candidate Details spreadsheet or fill the form manually.",
        "badge": None,
        "badge_colour": None,
    },
    {
        "key": "terms_conditions",
        "title": "Terms & Conditions",
        "description": "Terms of business with toggleable service types, fee structures, and guarantee periods. Auto-saves drafts.",
        "badge": "Draft save",
        "badge_colour": "#059669",
    },
    {
        "key": "contractor_agreement",
        "title": "Contractor Agreement",
        "description": "Sole trader or limited company agreements. Fill Schedule 1 details and generate a branded agreement.",
        "badge": "Draft save",
        "badge_colour": "#059669",
    },
]


def render(navigate):
    """Render the home page with document type cards."""
    st.markdown("")
    st.markdown(
        '<p style="font-size: 1.1rem; color: #6B7280; margin-bottom: 2rem;">'
        'Select a document type to get started.</p>',
        unsafe_allow_html=True,
    )

    cols = st.columns(2, gap="medium")
    for i, card in enumerate(DOCUMENT_CARDS):
        with cols[i % 2]:
            with st.container(border=True):
                # Badge + title row
                if card["badge"]:
                    st.markdown(
                        f'<span style="display:inline-block; font-size:0.7rem; '
                        f'font-weight:600; color:white; background:{card["badge_colour"]}; '
                        f'padding:2px 8px; border-radius:4px; margin-bottom:0.5rem;">'
                        f'{card["badge"]}</span>',
                        unsafe_allow_html=True,
                    )
                st.markdown(f"**{card['title']}**")
                st.markdown(
                    f'<p style="font-size:0.85rem; color:#6B7280; '
                    f'margin-bottom:1rem; line-height:1.5;">'
                    f'{card["description"]}</p>',
                    unsafe_allow_html=True,
                )
                if st.button(
                    "Open",
                    key=f"card_{card['key']}",
                    type="primary",
                    use_container_width=True,
                ):
                    navigate(card["key"])
                    st.rerun()
