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


async def send_insufficient_credits_email(
    recipient: str, name: str, checkout_url: str
) -> None:
    """Send an email when user has insufficient credits.

    Args:
        recipient: User's email address
        name: User's name
        checkout_url: URL to purchase credits
    """
    from config import FRONTEND_URL

    subject = "Purchase Credits to Generate Your NHS Supporting Information"
    body = f"""Dear {name},

Thank you for using the NHS Supporting Information Generator!

To generate your tailored supporting statement, you'll need to purchase credits first.

**[Purchase Credits Now]({checkout_url})**

Once your payment is complete, simply resubmit your application form and we'll generate your supporting information right away.

If you have any questions, please don't hesitate to reach out.

Best regards,
The NHS Supporting Information Generator Team"""

    await send_email(recipient, subject, body)
