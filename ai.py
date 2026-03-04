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
    referee_title: str,
    referee_previous: str,
    transcript: str,
) -> dict[str, str]:
    """Send transcript to Claude API, return dict of 26 answers.

    Returns:
        Dict with keys "0" through "25", each containing the answer text.

    Raises:
        ValueError: If the API response cannot be parsed as valid JSON.
    """
    client = Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

    system_prompt = _load_prompt("reference_check_system.txt")
    user_template = _load_prompt("reference_check_user.txt")

    user_message = user_template.format(
        candidate_name=candidate_name,
        position=position,
        referee_name=referee_name,
        referee_title=referee_title,
        referee_previous=referee_previous or "N/A",
        transcript=transcript,
    )

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=8192,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract text content
    text = response.content[0].text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text[:-3].strip()

    answers = json.loads(text)

    # Validate all 26 keys present
    for i in range(26):
        if str(i) not in answers:
            answers[str(i)] = "[GAP] Not addressed in transcript."

    return answers
