"""Claude API integration for document processing."""

import json
import streamlit as st
from anthropic import Anthropic
from pathlib import Path


PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(filename: str) -> str:
    """Load a prompt template from the prompts directory."""
    return (PROMPTS_DIR / filename).read_text(encoding="utf-8")


def process_reference_transcript(
    candidate_name: str,
    position: str,
    referee_name: str,
    referee_current_title: str,
    referee_current_company: str,
    referee_previous_title: str,
    referee_previous_company: str,
    transcript: str,
    additional_questions: list[str] | None = None,
) -> dict[str, str]:
    """Send transcript to Claude API, return dict of answers.

    Args:
        additional_questions: Optional list of custom reference questions.
            These are appended to the standard 26 with sequential indices
            starting at 26. The AI returns answers for all keys.

    Returns:
        Dict with keys "0" through f"{25 + len(additional_questions)}".

    Raises:
        ValueError: If the API response cannot be parsed as valid JSON.
    """
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    system_prompt = _load_prompt("reference_check_system.txt")
    user_template = _load_prompt("reference_check_user.txt")

    extras = additional_questions or []
    if extras:
        lines = ["", "ADDITIONAL QUESTIONS:"]
        for idx, q in enumerate(extras, start=26):
            lines.append(f"{idx}: {q}")
        additional_questions_block = "\n".join(lines) + "\n"
    else:
        additional_questions_block = ""

    user_message = user_template.format(
        candidate_name=candidate_name,
        position=position,
        referee_name=referee_name,
        referee_title=referee_current_title or "N/A",
        referee_current_company=referee_current_company or "N/A",
        referee_previous_title=referee_previous_title or "N/A",
        referee_previous_company=referee_previous_company or "N/A",
        transcript=transcript,
        additional_questions_block=additional_questions_block,
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text.strip()

    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()

    answers = json.loads(text)

    total = 26 + len(extras)
    for i in range(total):
        if str(i) not in answers:
            answers[str(i)] = "[GAP] Not addressed in transcript."

    return answers


def extract_cv_data(cv_text: str) -> dict:
    """Extract structured candidate data from CV text.

    Returns:
        Dict with keys: name, career (list), education_qualifications,
        notice_period, salary_expectation.
    """
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    prompt_template = _load_prompt("shortlist_extract.txt")
    user_message = prompt_template.format(cv_text=cv_text)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[{"role": "user", "content": user_message}],
    )

    text = response.content[0].text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()

    data = json.loads(text)

    # Ensure required keys exist
    data.setdefault("name", "Unknown")
    data.setdefault("career", [])
    data.setdefault("education_qualifications", "")
    data.setdefault("notice_period", "")
    data.setdefault("salary_expectation", "")

    return data


def proofread_notes(notes: str) -> str:
    """Proofread consultant notes — fix spelling/grammar, return corrected text."""
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    prompt_template = _load_prompt("shortlist_proofread.txt")
    user_message = prompt_template.format(notes=notes)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text.strip()


def redact_cv_text(cv_text: str) -> str:
    """Remove personal details, links, and references from CV text."""
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    prompt_template = _load_prompt("cv_redact.txt")
    user_message = prompt_template.format(cv_text=cv_text)

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        messages=[{"role": "user", "content": user_message}],
    )

    return response.content[0].text.strip()
