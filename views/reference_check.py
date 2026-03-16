"""Reference Check page — AI-powered transcript processing."""

import streamlit as st
from datetime import date
from ui import page_header, step_flow, form_section


def render():
    page_header("Reference Check", "AI-powered reference check from call transcripts")

    # Determine current step
    has_answers = "ref_answers" in st.session_state
    current_step = 1 if has_answers else 0
    step_flow(["Fill Details", "Review & Edit", "Download"], current_step)

    if not has_answers:
        _render_form()
    else:
        _render_review()


def _render_form():
    from ai import process_reference_transcript

    form_section("Details")
    col1, col2 = st.columns(2)
    with col1:
        candidate_name = st.text_input("Candidate name *")
        position = st.text_input("Role applied for *")
        completed_by = st.selectbox(
            "Completed by",
            ["Tate McClenaghan", "Jason Elston", "Kelsi Halliday", "Aimee"],
        )
    with col2:
        referee_name = st.text_input("Referee name *")
        referee_title = st.text_input("Referee current position")
        referee_previous = st.text_input("Referee previous position (optional)")

    form_section("Transcript")
    transcript = st.text_area(
        "Paste Granola transcript",
        height=300,
        placeholder="Paste the full reference call transcript here...",
        label_visibility="collapsed",
    )

    st.markdown("")
    col_btn, col_space = st.columns([1, 2])
    with col_btn:
        generate = st.button("Generate Reference", type="primary", width="stretch")

    if generate:
        if not candidate_name or not position or not referee_name:
            st.error("Please fill in all required fields (marked with *).")
        elif not transcript.strip():
            st.error("Please paste the transcript.")
        else:
            with st.spinner("Processing transcript with AI..."):
                try:
                    answers = process_reference_transcript(
                        candidate_name=candidate_name,
                        position=position,
                        referee_name=referee_name,
                        referee_title=referee_title,
                        referee_previous=referee_previous,
                        transcript=transcript,
                    )
                    st.session_state.ref_answers = answers
                    st.session_state.ref_metadata = {
                        "candidate_name": candidate_name,
                        "position": position,
                        "referee_name": referee_name,
                        "referee_title": referee_title,
                        "referee_previous": referee_previous,
                        "completed_by": completed_by,
                        "reference_date": date.today().strftime("%d/%m/%Y"),
                    }
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing transcript: {e}")


def _render_review():
    from generators.reference_check import generate_docx, QUESTIONS

    # Back button
    if st.button("< Back to form"):
        del st.session_state["ref_answers"]
        del st.session_state["ref_metadata"]
        st.rerun()

    form_section("Review & Edit Answers")
    st.caption("Edit any answer below before downloading. Flagged items need your attention.")

    answers = st.session_state.ref_answers
    edited_answers = {}

    for i, question in enumerate(QUESTIONS):
        key = str(i)
        current = answers.get(key, "")
        is_gap = current.startswith("[GAP]")

        label = f"Q{i+1}: {question}"
        if is_gap:
            label += "  ⚠️ NEEDS REVIEW"

        edited = st.text_area(
            label,
            value=current.replace("[GAP] ", ""),
            height=120 if len(current) > 200 else 80,
            key=f"answer_{i}",
        )
        edited_answers[key] = edited

    # Download
    st.divider()
    metadata = st.session_state.ref_metadata
    data = {**metadata, "answers": edited_answers}

    try:
        docx_bytes = generate_docx(data)
        filename = (
            f"Reference Check for {metadata['candidate_name']} "
            f"from {metadata['referee_name']}.docx"
        )
        st.download_button(
            label="Download .docx",
            data=docx_bytes,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            type="primary",
        )
    except Exception as e:
        st.error(f"Error generating document: {e}")
