import base64

from anthropic import Anthropic

from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from services.pdf_extractor import download_file, extract_text_from_pdf_bytes

SYSTEM_PROMPT = """You are an expert NHS job application writer specialising in creating compelling Supporting Information statements.
Your role is to analyse a candidate's CV alongside the Person Specification for a specific role, then produce a well-structured, professional statement.

Guidelines:
- Address each criterion in the Person Specification systematically
- Draw specific evidence from the candidate's CV to support each point
- Use the STAR method (Situation, Task, Action, Result) where appropriate
- Align the statement with NHS values and the specific Trust's ethos
- Write in first person from the candidate's perspective
- Be specific — avoid generic statements
- Demonstrate genuine passion for nursing/midwifery care
- Structure the response with clear headings that match the Person Specification criteria
- Keep a professional yet warm tone throughout"""


def _get_media_type(filename: str) -> str:
    """Derive image MIME type from filename extension."""
    if filename.lower().endswith(".png"):
        return "image/png"
    return "image/jpeg"  # covers .jpg and .jpeg


async def generate_supporting_info(
    name: str,
    role: str,
    trust: str,
    cv_url: str,
    person_spec_url: str,
    person_spec_filename: str,
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
    media_type = _get_media_type(person_spec_filename)

    user_prompt = (
        f"Please generate a Supporting Information statement for the following application:\n\n"
        f"Candidate: {name}\n"
        f"Role: {role}\n"
        f"NHS Trust: {trust}\n\n"
        f"--- CV TEXT ---\n"
        f"{cv_text}\n"
        f"--- END CV ---\n\n"
        f"The Person Specification is in the attached image above.\n"
        f"Analyse both documents and produce the Supporting Information statement, "
        f"addressing each criterion from the Person Specification with evidence from the CV."
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
