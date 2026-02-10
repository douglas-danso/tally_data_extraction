import base64
import json
from pathlib import Path

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from services.pdf_extractor import download_file, extract_text_from_pdf_bytes
from services.prompts import SYSTEM_PROMPT_DEFAULT, SYSTEM_PROMPT_SCOTLAND


def load_statement_formats() -> dict:
    """Load statement formats configuration from JSON file."""
    formats_path = Path(__file__).parent.parent / "statement_formats.json"
    with open(formats_path, "r") as f:
        return json.load(f)


def get_statement_format(trust_name: str) -> str:
    """Determine which statement format to use based on the trust."""
    formats = load_statement_formats()

    # Check if trust is in Scotland format list
    scotland_trusts = formats.get("scotland_3_questions", {}).get("trusts", [])
    for scotland_trust in scotland_trusts:
        if scotland_trust.lower() in trust_name.lower() or trust_name.lower() in scotland_trust.lower():
            return "scotland_3_questions"

    # Default format for all other trusts
    return "default"


def load_trust_values() -> dict:
    """Load trust values from JSON file."""
    trust_values_path = Path(__file__).parent.parent / "trust_values.json"
    with open(trust_values_path, "r") as f:
        return json.load(f)


def get_trust_values_text(trust_name: str) -> str:
    """Get formatted trust values text for a specific trust."""
    trust_data = load_trust_values()

    # Try exact match first
    if trust_name in trust_data:
        trust_info = trust_data[trust_name]
        values_list = ", ".join(trust_info["values"])
        return f"Trust Values: {values_list}\nDescription: {trust_info['description']}"

    # Try partial match (case-insensitive)
    trust_name_lower = trust_name.lower()
    for trust_key, trust_info in trust_data.items():
        if trust_name_lower in trust_key.lower() or trust_key.lower() in trust_name_lower:
            values_list = ", ".join(trust_info["values"])
            return f"Trust Values: {values_list}\nDescription: {trust_info['description']}"

    # If no match found, return generic NHS values
    return "Trust Values: Not specified (please use general NHS values: Compassion, Respect, Excellence, Teamwork)"


async def generate_supporting_info(
    name: str,
    role: str,
    trust: str,
    cv_url: str,
    person_spec_url: str,
    person_spec_mimetype: str,
) -> str:
    """Download CV + Person Spec, feed both to Claude, return the statement."""
    client = Anthropic(api_key=ANTHROPIC_API_KEY)

    # Download files in parallel
    import asyncio

    cv_bytes, ps_bytes = await asyncio.gather(
        download_file(cv_url),
        download_file(person_spec_url),
    )

    # Extract CV text from PDF
    cv_text = extract_text_from_pdf_bytes(cv_bytes)

    # Check if CV extraction was successful
    if not cv_text or len(cv_text.strip()) < 50:
        raise ValueError(
            "CV text extraction failed or CV appears to be empty. "
            "Please ensure the CV is a text-based PDF (not a scanned image). "
            "If the CV is a scanned document, please convert it to a text-based PDF first."
        )

    # Encode Person Spec image for Claude vision
    ps_base64 = base64.standard_b64encode(ps_bytes).decode("utf-8")
    media_type = person_spec_mimetype

    # Get trust values and determine format
    trust_values_text = get_trust_values_text(trust)
    statement_format = get_statement_format(trust)

    # Select appropriate system prompt based on format
    if statement_format == "scotland_3_questions":
        system_prompt = SYSTEM_PROMPT_SCOTLAND
        word_limit = "1,250"
        format_description = "three-question format (Q1: 500 words, Q2: 500 words, Q3: 250 words)"
    else:
        system_prompt = SYSTEM_PROMPT_DEFAULT
        word_limit = "1,500"
        format_description = "standard NHS England format"

    user_prompt = (
        f"⚠️ CRITICAL: The Supporting Information MUST NOT EXCEED {word_limit} WORDS. This is a hard limit. ⚠️\n\n"
        f"Please generate Supporting Information for the following application:\n\n"
        f"Candidate: {name}\n"
        f"Role: {role}\n"
        f"NHS Trust: {trust}\n"
        f"Format: {format_description}\n\n"
        f"--- TRUST VALUES ---\n"
        f"{trust_values_text}\n"
        f"--- END TRUST VALUES ---\n\n"
        f"--- CV TEXT ---\n"
        f"{cv_text}\n"
        f"--- END CV ---\n\n"
        f"The Person Specification is in the attached image above.\n\n"
        f"Analyse all documents (CV, Person Specification, and Trust Values) and produce the Supporting Information, "
        f"addressing each criterion from the Person Specification with evidence from the CV, "
        f"and aligning with the Trust Values provided.\n\n"
        f"⚠️ CRITICAL OUTPUT INSTRUCTIONS: ⚠️\n"
        f"1. Generate the response following all requirements in the system prompt\n"
        f"2. Count the total words\n"
        f"3. If over {word_limit} words, trim it down internally\n"
        f"4. Follow the exact output format specified in the system prompt\n\n"
        f"⚠️ You MUST provide the COMPLETE final response after the word count line. "
        f"Do NOT stop after just showing the word count or saying you need to reduce it. "
        f"Provide the full trimmed response that is ready to use. ⚠️"
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": ps_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": user_prompt,
                    },
                ],
            }
        ],
    )

    return message.content[0].text
