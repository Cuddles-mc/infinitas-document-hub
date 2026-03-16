"""Home page — simple welcome message."""

import streamlit as st


def render(navigate):
    st.markdown("")
    st.markdown("")
    st.markdown(
        '<div style="text-align: center; padding: 3rem 1rem;">'
        '<p style="font-size: 1.3rem; color: #6B7280; margin-bottom: 0.5rem;">'
        'Welcome to the Document Hub</p>'
        '<p style="font-size: 0.95rem; color: #9CA3AF;">'
        'Select a tool from the sidebar to get started.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
