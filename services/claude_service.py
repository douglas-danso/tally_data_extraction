import base64
import json
from pathlib import Path

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from services.pdf_extractor import download_file, extract_text_from_pdf_bytes

SYSTEM_PROMPT = """You are an NHS Supporting Statement writing assistant.

Your task is to generate a Supporting Statement with a HARD MAXIMUM of 1,500 words.

Do not exceed 1,500 words under any circumstances.

The statement must be written in the first person ("I") and sound human, professional, and natural — not robotic or AI-generated and avoid m dash.

Avoid generic phrases such as:
- "I am passionate about…"
- "I bring a unique blend…"
- "I am excited to apply…"
- "leveraging my skills"
- "dynamic environment"
- "results-driven"
- "synergy"

Keep language simple, direct, and NHS-appropriate.

---

CRITICAL RULES:

1. Use ONLY experience, qualifications, employers, locations, and responsibilities explicitly stated in the CV.
Do NOT invent hospitals, wards, patients, treatments, employers, or scenarios.

2. Every criterion listed in the Person Specification MUST be covered independently as its own subheading.

3. For EACH ESSENTIAL criterion:
   - Provide a real example from the CV.
   - Embed the example directly under that criterion.
   - Reference real workplaces or geographical locations where possible.
   - Let examples flow naturally (do NOT label as "STAR" or "Example").

4. If the applicant lacks direct experience for a criterion:
   - Use relevant TRANSFERABLE skills from the CV.
   - Clearly explain how these skills apply to the requirement.
   - Do not imply clinical exposure if it does not exist.

5. Maintain the exact order of criteria as presented in the Person Specification (including Essential and Desirable).

6. Align with Trust Values using real behaviours or experience from the CV.

7. Keep total output under 1,500 words.

---

REQUIRED FORMAT (must follow exactly):

1. Introduction

2. Aligning With Trust Values
   - Each Trust Value must be listed independently as a subheading.
   - Under each value, explain alignment using CV-based experience.

3. Person Specification Criteria
   - Use the main headings from the Person Specification.
   - Under each, list EVERY Essential and Desirable criterion as its own subheading.
   - Clinical or professional examples must sit directly under the relevant criterion.

4. What Sets Me Apart

5. Conclusion

---

STYLE REQUIREMENTS:

- Human, professional NHS tone.
- First person ("I").
- No exaggerated claims.
- No invented experience.
- Clear, concise paragraphs.
- Emphasis on patient safety, teamwork, communication, documentation, safeguarding, professionalism, and compassionate care where supported by CV evidence.

---

INPUTS:

Applicant CV:
{{CV_TEXT}}

Person Specification:
{{PERSON_SPECIFICATION}}

Trust Values:
{{TRUST_VALUES}}

---

FINAL OUTPUT:

Produce a complete NHS Supporting Statement under 1,500 words that:

- Covers every criterion independently
- Uses only CV evidence
- Embeds real examples under Essential criteria
- Applies transferable skills where direct experience is missing
- Aligns clearly with Trust Values
- Reads naturally as if written by the applicant"""


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

    # Encode Person Spec image for Claude vision
    ps_base64 = base64.standard_b64encode(ps_bytes).decode("utf-8")
    media_type = person_spec_mimetype

    # Get trust values
    trust_values_text = get_trust_values_text(trust)

    user_prompt = (
        f"Please generate a Supporting Information statement for the following application:\n\n"
        f"Candidate: {name}\n"
        f"Role: {role}\n"
        f"NHS Trust: {trust}\n\n"
        f"--- TRUST VALUES ---\n"
        f"{trust_values_text}\n"
        f"--- END TRUST VALUES ---\n\n"
        f"--- CV TEXT ---\n"
        f"{cv_text}\n"
        f"--- END CV ---\n\n"
        f"The Person Specification is in the attached image above.\n"
        f"Analyse all documents (CV, Person Specification, and Trust Values) and produce the Supporting Information statement, "
        f"addressing each criterion from the Person Specification with evidence from the CV, "
        f"and aligning with the Trust Values provided."
    )

    message = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=4000,
        system=SYSTEM_PROMPT,
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
