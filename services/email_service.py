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
    """Send a styled email when user has insufficient credits.

    Args:
        recipient: User's email address
        name: User's name
        checkout_url: URL to purchase credits
    """
    subject = "Purchase Credits to Generate Your NHS Supporting Information"

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:'Segoe UI',Arial,Helvetica,sans-serif;color:#333333;">
  <!-- Wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
    <tr>
      <td align="center" style="padding:24px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#ffffff;border-radius:12px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background-color:#1a1a2e;padding:32px 40px;text-align:center;">
              <h1 style="margin:0;font-size:26px;font-weight:700;color:#ffffff;letter-spacing:0.5px;">ApplySmartUK</h1>
              <p style="margin:6px 0 0;font-size:13px;color:#b0b0c8;">Your no.1 NHS application support in one space!</p>
            </td>
          </tr>

          <!-- Greeting & Main Content -->
          <tr>
            <td style="padding:32px 40px 16px;">
              <p style="margin:0;font-size:16px;line-height:1.6;">Dear <strong>{name}</strong>,</p>
              <p style="margin:12px 0 0;font-size:15px;line-height:1.6;color:#555555;">
                Thank you for using the NHS Supporting Information Generator!
              </p>
              <p style="margin:12px 0 0;font-size:15px;line-height:1.6;color:#555555;">
                To generate your tailored supporting statement, you'll need to purchase credits first.
              </p>
            </td>
          </tr>

          <!-- CTA Button -->
          <tr>
            <td style="padding:16px 40px;text-align:center;">
              <table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 auto;">
                <tr>
                  <td style="background-color:#f0c14b;border-radius:6px;padding:14px 28px;">
                    <a href="{checkout_url}" style="font-size:16px;font-weight:700;color:#1a1a2e;text-decoration:none;display:inline-block;">Purchase Credits Now</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Next Steps -->
          <tr>
            <td style="padding:16px 40px 24px;">
              <p style="margin:0;font-size:15px;line-height:1.6;color:#555555;">
                Once your payment is complete, simply resubmit your application form and we'll generate your supporting information right away.
              </p>
              <p style="margin:16px 0 0;font-size:14px;line-height:1.6;color:#555555;">
                If you have any questions, please don't hesitate to reach out. Good luck with your application!
              </p>
            </td>
          </tr>

          <!-- Sign-off -->
          <tr>
            <td style="padding:0 40px 32px;">
              <p style="margin:0;font-size:15px;color:#333333;">Best regards,</p>
              <p style="margin:4px 0 0;font-size:16px;font-weight:700;color:#1a1a2e;">ApplySmartUK</p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:0 40px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e8e8e8;">
                <tr>
                  <td style="padding-top:20px;">
                    <p style="margin:0;font-size:13px;color:#888888;text-align:center;">
                      <a href="mailto:Info@ApplySmartUK.UK" style="color:#2a6496;text-decoration:none;">Info@ApplySmartUK.UK</a>
                    </p>
                    <p style="margin:16px 0 0;font-size:12px;color:#aaaaaa;text-align:center;line-height:1.6;">
                      <strong style="color:#888888;">Refund Policy</strong><br/>
                      Due to the digital and automated nature of this product, all purchases are final.
                      Once a supporting statement has been generated and delivered, refunds cannot be issued.
                      If you experience a technical issue preventing generation, please contact us within 24 hours,
                      and we will resolve the issue promptly.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    plain_text = f"""Dear {name},

Thank you for using the NHS Supporting Information Generator!

To generate your tailored supporting statement, you'll need to purchase credits first.

Purchase Credits Now: {checkout_url}

Once your payment is complete, simply resubmit your application form and we'll generate your supporting information right away.

If you have any questions, please don't hesitate to reach out.

Best regards,
ApplySmartUK Team
Info@ApplySmartUK.UK"""

    await send_confirmation_html_email(recipient, subject, html_body, plain_text)


async def send_order_confirmation_email(
    recipient: str, customer_name: str = "there"
) -> None:
    """Send a branded order confirmation email after successful payment.

    Args:
        recipient: Customer's email address
        customer_name: Customer's name (defaults to "there" for "Hi there,")
    """
    subject = "Your Order from @ApplySmartUK is here!"

    html_body = f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f4;font-family:'Segoe UI',Arial,Helvetica,sans-serif;color:#333333;">
  <!-- Wrapper -->
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f4;">
    <tr>
      <td align="center" style="padding:24px 16px;">
        <table role="presentation" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background-color:#ffffff;border-radius:12px;overflow:hidden;">

          <!-- Header -->
          <tr>
            <td style="background-color:#1a1a2e;padding:32px 40px;text-align:center;">
              <h1 style="margin:0;font-size:26px;font-weight:700;color:#ffffff;letter-spacing:0.5px;">ApplySmartUK</h1>
              <p style="margin:6px 0 0;font-size:13px;color:#b0b0c8;">Your no.1 NHS application support in one space!</p>
            </td>
          </tr>

          <!-- Greeting -->
          <tr>
            <td style="padding:32px 40px 16px;">
              <p style="margin:0;font-size:16px;line-height:1.6;">Hi <strong>{customer_name}</strong>,</p>
              <p style="margin:12px 0 0;font-size:15px;line-height:1.6;color:#555555;">
                Thanks for your purchase &mdash; you&rsquo;re all set to generate your NHS supporting information!
              </p>
              <p style="margin:12px 0 0;font-size:15px;line-height:1.6;color:#555555;">Here&rsquo;s what to do next.</p>
            </td>
          </tr>

          <!-- Section title -->
          <tr>
            <td style="padding:8px 40px 0;">
              <h2 style="margin:0;font-size:18px;font-weight:700;color:#1a1a2e;text-transform:uppercase;letter-spacing:0.5px;border-bottom:3px solid #f0c14b;display:inline-block;padding-bottom:4px;">
                Write Your Supporting Information
              </h2>
            </td>
          </tr>

          <!-- Step 1 -->
          <tr>
            <td style="padding:20px 40px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="44" valign="top" style="padding-top:2px;">
                    <div style="width:36px;height:36px;border-radius:50%;background-color:#f0c14b;color:#1a1a2e;font-weight:700;font-size:16px;text-align:center;line-height:36px;">1</div>
                  </td>
                  <td style="padding-left:12px;">
                    <p style="margin:0;font-size:15px;font-weight:700;color:#1a1a2e;">Find your job advert</p>
                    <ul style="margin:8px 0 0;padding-left:18px;font-size:14px;line-height:1.7;color:#555555;">
                      <li>Go to the NHS Jobs website.</li>
                      <li>Open the vacancy you&rsquo;re applying for.</li>
                    </ul>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Step 2 -->
          <tr>
            <td style="padding:20px 40px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="44" valign="top" style="padding-top:2px;">
                    <div style="width:36px;height:36px;border-radius:50%;background-color:#f0c14b;color:#1a1a2e;font-weight:700;font-size:16px;text-align:center;line-height:36px;">2</div>
                  </td>
                  <td style="padding-left:12px;">
                    <p style="margin:0;font-size:15px;font-weight:700;color:#1a1a2e;">Download the Person Specification &amp; take a screenshot <span style="font-size:13px;color:#c0392b;">(Screenshot ONLY!)</span></p>
                    <ul style="margin:8px 0 0;padding-left:18px;font-size:14px;line-height:1.7;color:#555555;">
                      <li>Scroll to the bottom or right side of the advert.</li>
                      <li>Download the document called <strong>Person Specification</strong> (sometimes titled <em>PS</em>).</li>
                      <li>This is required to generate your statement.</li>
                    </ul>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Step 3 -->
          <tr>
            <td style="padding:20px 40px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="44" valign="top" style="padding-top:2px;">
                    <div style="width:36px;height:36px;border-radius:50%;background-color:#f0c14b;color:#1a1a2e;font-weight:700;font-size:16px;text-align:center;line-height:36px;">3</div>
                  </td>
                  <td style="padding-left:12px;">
                    <p style="margin:0;font-size:15px;font-weight:700;color:#1a1a2e;">Prepare your files</p>
                    <ul style="margin:8px 0 0;padding-left:18px;font-size:14px;line-height:1.7;color:#555555;">
                      <li>Save your CV.</li>
                      <li>Save the Person Specification screenshot.</li>
                      <li>Keep both in the same folder on your device, for ease.</li>
                    </ul>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Step 4 -->
          <tr>
            <td style="padding:20px 40px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td width="44" valign="top" style="padding-top:2px;">
                    <div style="width:36px;height:36px;border-radius:50%;background-color:#f0c14b;color:#1a1a2e;font-weight:700;font-size:16px;text-align:center;line-height:36px;">4</div>
                  </td>
                  <td style="padding-left:12px;">
                    <p style="margin:0;font-size:15px;font-weight:700;color:#1a1a2e;">Generate your supporting information</p>
                    <ul style="margin:8px 0 0;padding-left:18px;font-size:14px;line-height:1.7;color:#555555;">
                      <li>Go to: <a href="https://tally.so/r/KY1l77" style="color:#2a6496;text-decoration:underline;font-weight:600;">Generate Supporting Information</a></li>
                      <li>Upload your CV.</li>
                      <li>Upload the Person Specification.</li>
                      <li>Submit the form.</li>
                    </ul>
                    <p style="margin:10px 0 0;font-size:14px;line-height:1.6;color:#555555;">
                      Your tailored NHS supporting information will be generated shortly and sent to the email address you provided.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Tip box -->
          <tr>
            <td style="padding:24px 40px 0;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#fef9e7;border-left:4px solid #f0c14b;border-radius:6px;">
                <tr>
                  <td style="padding:16px 20px;">
                    <p style="margin:0;font-size:14px;font-weight:700;color:#1a1a2e;">&#128161; Tip</p>
                    <p style="margin:8px 0 0;font-size:13px;line-height:1.6;color:#555555;">
                      For best results, upload your most updated CV and a clear Person Specification screenshot and review the final statement before submitting your application. <strong>Always review the supporting statement before submitting!</strong>
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- Help line -->
          <tr>
            <td style="padding:24px 40px 0;">
              <p style="margin:0;font-size:14px;line-height:1.6;color:#555555;">
                If you have any issues or questions, reply to this email. Good luck with your application!
              </p>
            </td>
          </tr>

          <!-- Sign-off -->
          <tr>
            <td style="padding:24px 40px 0;">
              <p style="margin:0;font-size:15px;color:#333333;">Best,</p>
              <p style="margin:4px 0 0;font-size:16px;font-weight:700;color:#1a1a2e;">ApplySmartUK</p>
              <p style="margin:2px 0 0;font-size:13px;color:#888888;">&mdash; NHS Supporting Information Generator</p>
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding:28px 40px 32px;">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-top:1px solid #e8e8e8;">
                <tr>
                  <td style="padding-top:20px;">
                    <p style="margin:0;font-size:13px;color:#888888;text-align:center;">
                      <a href="mailto:Info@ApplySmartUK.UK" style="color:#2a6496;text-decoration:none;">Info@ApplySmartUK.UK</a>
                    </p>
                    <p style="margin:16px 0 0;font-size:12px;color:#aaaaaa;text-align:center;line-height:1.6;">
                      <strong style="color:#888888;">Refund Policy</strong><br/>
                      Due to the digital and automated nature of this product, all purchases are final.
                      Once a supporting statement has been generated and delivered, refunds cannot be issued.
                      If you experience a technical issue preventing generation, please contact us within 24 hours,
                      and we will resolve the issue promptly.
                    </p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""

    # Plain-text fallback
    plain_text = f"""Hi {customer_name},

Thanks for your purchase — you're all set to generate your NHS supporting information!

Here's what to do next.

WRITE YOUR SUPPORTING INFORMATION

Step 1 – Find your job advert
- Go to the NHS Jobs website.
- Open the vacancy you're applying for.

Step 2 – Download the Person Specification & take a screenshot (Screenshot ONLY!)
- Scroll to the bottom or right side of the advert.
- Download the document called Person Specification (sometimes titled PS).
- This is required to generate your statement.

Step 3 – Prepare your files
- Save your CV.
- Save the Person Specification screenshot.
- Keep both in the same folder on your device, for ease.

Step 4 – Generate your supporting information
- Go to: https://tally.so/r/KY1l77
- Upload your CV.
- Upload the Person Specification.
- Submit the form.

Your tailored NHS supporting information will be generated shortly and sent to the email address you provided.

Tip: For best results, upload your most updated CV and a clear Person Specification screenshot and review the final statement before submitting your application. Always review the supporting statement before submitting!

If you have any issues or questions, reply to this email. Good luck with your application!

Best,
ApplySmartUK
— NHS Supporting Information Generator
Info@ApplySmartUK.UK

Refund Policy
Due to the digital and automated nature of this product, all purchases are final.
Once a supporting statement has been generated and delivered, refunds cannot be issued.
If you experience a technical issue preventing generation, please contact us within 24 hours, and we will resolve the issue promptly."""

    await send_confirmation_html_email(recipient, subject, html_body, plain_text)


async def send_confirmation_html_email(
    recipient: str, subject: str, html_body: str, plain_text: str
) -> None:
    """Send an HTML email with a plain-text fallback via Brevo.

    Unlike send_email(), this accepts pre-built HTML rather than
    converting Markdown.
    """
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": BREVO_API_KEY},
            json={
                "sender": {"email": BREVO_FROM_EMAIL},
                "to": [{"email": recipient}],
                "subject": subject,
                "htmlContent": html_body,
                "textContent": plain_text,
            },
            timeout=30.0,
        )
        response.raise_for_status()
