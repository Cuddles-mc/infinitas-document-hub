"""Reference Check page — AI-powered transcript processing."""

import streamlit as st
from datetime import date
from ui import page_header, step_flow, form_section


def render():
    page_header("Reference Check", "AI-powered reference check from call transcripts")

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
            ["Tate McClenaghan", "Jason Beith", "Kelsi Flynn", "Katie Scott"],
        )
    with col2:
        referee_name = st.text_input("Referee name *")
        referee_current_title = st.text_input("Referee current position")
        referee_current_company = st.text_input("Referee current employer")

    st.markdown("")
    col3, col4 = st.columns(2)
    with col3:
        referee_previous_title = st.text_input(
            "Referee previous position (optional)",
            help="If different from when they worked with the candidate",
        )
    with col4:
        referee_previous_company = st.text_input(
            "Referee previous employer (optional)",
        )

    form_section("Transcript")
    transcript = st.text_area(
        "Paste Granola transcript",
        height=300,
        placeholder="Paste the full reference call transcript here...",
        label_visibility="collapsed",
    )

    form_section("Additional questions (optional)")
    extra_questions_raw = st.text_area(
        "One question per line. Leave blank to use the standard 26.",
        height=100,
        placeholder="e.g.\nWould you place them in a Crown Entity governance role?\nDid they ever lead a regulated programme of work?",
        key="ref_extra_questions",
    )

    st.markdown("")
    col_btn, _ = st.columns([1, 2])
    with col_btn:
        generate = st.button("Generate Reference", type="primary", width="stretch")

    if generate:
        if not candidate_name or not position or not referee_name:
            st.error("Please fill in all required fields (marked with *).")
        elif not transcript.strip():
            st.error("Please paste the transcript.")
        else:
            additional_questions = [
                q.strip() for q in extra_questions_raw.splitlines() if q.strip()
            ]
            with st.spinner("Processing transcript with AI..."):
                try:
                    answers = process_reference_transcript(
                        candidate_name=candidate_name,
                        position=position,
                        referee_name=referee_name,
                        referee_current_title=referee_current_title,
                        referee_current_company=referee_current_company,
                        referee_previous_title=referee_previous_title,
                        referee_previous_company=referee_previous_company,
                        transcript=transcript,
                        additional_questions=additional_questions or None,
                    )
                    st.session_state.ref_answers = answers
                    st.session_state.ref_metadata = {
                        "candidate_name": candidate_name,
                        "position": position,
                        "referee_name": referee_name,
                        "referee_current_title": referee_current_title,
                        "referee_current_company": referee_current_company,
                        "referee_previous_title": referee_previous_title,
                        "referee_previous_company": referee_previous_company,
                        "completed_by": completed_by,
                        "reference_date": date.today().strftime("%d/%m/%Y"),
                    }
                    st.session_state.ref_additional_questions = additional_questions
                    st.rerun()
                except Exception as e:
                    st.error(f"Error processing transcript: {e}")


def _render_review():
    from generators.reference_check import generate_docx, STANDARD_QUESTIONS

    if st.button("< Back to form"):
        for k in ("ref_answers", "ref_metadata", "ref_additional_questions"):
            st.session_state.pop(k, None)
        st.rerun()

    form_section("Review & Edit Answers")
    st.caption("Edit any answer below before downloading. Flagged items need your attention.")

    answers = st.session_state.ref_answers
    additional_questions = st.session_state.get("ref_additional_questions", []) or []
    questions = list(STANDARD_QUESTIONS) + list(additional_questions)
    edited_answers = {}

    for i, question in enumerate(questions):
        key = str(i)
        current = answers.get(key, "")
        is_gap = current.startswith("[GAP]")
        is_extra = i >= len(STANDARD_QUESTIONS)

        label = f"Q{i + 1}: {question}"
        if is_extra:
            label = f"Q{i + 1} (additional): {question}"
        if is_gap:
            label += "  ⚠️ NEEDS REVIEW"

        edited = st.text_area(
            label,
            value=current.replace("[GAP] ", ""),
            height=120 if len(current) > 200 else 80,
            key=f"answer_{i}",
        )
        edited_answers[key] = edited

    st.divider()
    metadata = st.session_state.ref_metadata
    data = {**metadata, "answers": edited_answers}

    try:
        docx_bytes = generate_docx(data, questions=questions)
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
