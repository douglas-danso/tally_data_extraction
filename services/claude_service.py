import base64
import json
from pathlib import Path

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from services.pdf_extractor import download_file, extract_text_from_pdf_bytes

SYSTEM_PROMPT = """You are an NHS Supporting Statement writing assistant.

═══════════════════════════════════════════════════════════════
⚠️  ABSOLUTE WORD LIMIT: 1,500 WORDS MAXIMUM ⚠️
DO NOT EXCEED 1,500 WORDS UNDER ANY CIRCUMSTANCES
THIS IS THE MOST IMPORTANT CONSTRAINT
═══════════════════════════════════════════════════════════════

Your task is to generate a Supporting Statement that:
- MUST be under 1,500 words (this is non-negotiable)
- Is written in first person ("I")
- Sounds human, professional, and natural — not robotic or AI-generated
- Avoids em dashes (use commas or periods instead)

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

1. WORD COUNT: The entire statement MUST be under 1,500 words. Be concise and focused.

2. Use ONLY experience, qualifications, employers, locations, and responsibilities explicitly stated in the CV.
   Do NOT invent hospitals, wards, patients, treatments, employers, or scenarios.

3. Every criterion listed in the Person Specification MUST be covered independently as its own subheading.

4. For EACH ESSENTIAL criterion:
   - Provide a real example from the CV.
   - Embed the example directly under that criterion.
   - Reference real workplaces or geographical locations where possible.
   - Let examples flow naturally (do NOT label as "STAR" or "Example").
   - Keep examples BRIEF to manage word count.

5. If the applicant lacks direct experience for a criterion:
   - Use relevant TRANSFERABLE skills from the CV.
   - Clearly explain how these skills apply to the requirement.
   - Do not imply clinical exposure if it does not exist.

6. Maintain the exact order of criteria as presented in the Person Specification (including Essential and Desirable).

7. Align with Trust Values using real behaviours or experience from the CV. Keep this section CONCISE.

---

REQUIRED FORMAT (must follow exactly):

1. Introduction (keep brief - 50-75 words)

2. Aligning With Trust Values (keep concise - aim for 150-200 words total)
   - Each Trust Value must be listed independently as a subheading.
   - Under each value, explain alignment using CV-based experience in 2-3 sentences.

3. Person Specification Criteria (this is the main section)
   - Use the main headings from the Person Specification.
   - Under each, list EVERY Essential and Desirable criterion as its own subheading.
   - Clinical or professional examples must sit directly under the relevant criterion.
   - Keep each criterion response to 50-80 words maximum.

4. What Sets Me Apart (keep brief - 75-100 words)

5. Conclusion (keep brief - 50-75 words)

REMEMBER: The total word count across ALL sections must not exceed 1,500 words.

---

STYLE REQUIREMENTS:

- Human, professional NHS tone.
- First person ("I").
- No exaggerated claims.
- No invented experience.
- Clear, concise paragraphs.
- Emphasis on patient safety, teamwork, communication, documentation, safeguarding, professionalism, and compassionate care where supported by CV evidence.
- CONCISE writing - every word must count toward the 1,500 word limit.

---

FINAL OUTPUT:

Produce a complete NHS Supporting Statement that:

- STAYS UNDER 1,500 WORDS (this is mandatory)
- Covers every criterion independently
- Uses only CV evidence
- Embeds real examples under Essential criteria
- Applies transferable skills where direct experience is missing
- Aligns clearly with Trust Values
- Reads naturally as if written by the applicant

REMEMBER: Check your word count. If approaching 1,500 words, make your writing more concise."""


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
        f"⚠️ CRITICAL: The Supporting Information statement MUST NOT EXCEED 1,500 WORDS. This is a hard limit. ⚠️\n\n"
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
        f"The Person Specification is in the attached image above.\n\n"
        f"Analyse all documents (CV, Person Specification, and Trust Values) and produce the Supporting Information statement, "
        f"addressing each criterion from the Person Specification with evidence from the CV, "
        f"and aligning with the Trust Values provided.\n\n"
        f"⚠️ REMINDER: Keep the total word count UNDER 1,500 WORDS. Be concise and focused. "
        f"If you find yourself approaching the limit, prioritize essential criteria and make your writing more compact. ⚠️"
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
