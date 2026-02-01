import markdown as md
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import aiosmtplib

from config import SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER


async def send_email(recipient: str, subject: str, body: str) -> None:
    """Send the Supporting Information to the applicant as a formatted HTML email.

    The body is expected in Markdown. It is converted to HTML for the primary
    part; a plain-text copy is attached as fallback.
    """
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = recipient

    # Plain-text fallback
    msg.attach(MIMEText(body, "plain"))

    # HTML — convert markdown and wrap in minimal styled shell
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
    msg.attach(MIMEText(html_body, "html"))

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=True,
    )
