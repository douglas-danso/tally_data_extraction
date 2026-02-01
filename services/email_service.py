import markdown as md

import httpx

from config import BREVO_API_KEY, BREVO_FROM_EMAIL


async def send_email(recipient: str, subject: str, body: str) -> None:
    """Send the Supporting Information via the Brevo API.

    The body is expected in Markdown. It is converted to styled HTML for
    delivery; a plain-text copy is included as fallback.
    """
    html_content = md.markdown(body, extensions=["nl2br"])
    html_body = (
        "<html><head><style>"
        "body { font-family: Arial, sans-serif; line-height: 1.6; "
        "max-width: 800px; margin: 0 auto; padding: 20px; color: #333; }"
        "h1, h2, h3 { color: #003087; }"
        "hr { border: none; border-top: 1px solid #ddd; margin: 24px 0; }"
        "</style></head>"
        f"<body>{html_content}</body></html>"
    )

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY},
            json={
                "sender": {"email": BREVO_FROM_EMAIL},
                "to": [{"email": recipient}],
                "subject": subject,
                "htmlContent": html_body,
                "textContent": body,
            },
            timeout=30.0,
        )
        response.raise_for_status()
