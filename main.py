import logging

from fastapi import FastAPI, HTTPException

from models import TallyWebhookPayload
from services.claude_service import generate_supporting_info
from services.email_service import send_email
from services.tally_parser import extract_fields

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="NHS Supporting Information Generator")


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/webhook")
async def tally_webhook(payload: TallyWebhookPayload):
    print(payload)
    """Receive and process a Tally form submission."""
    logger.info("Received submission for form: %s", payload.data.formName)

    # 1. Parse the Tally payload into structured fields
    try:
        form_data = extract_fields(payload)
    except (KeyError, ValueError, IndexError) as e:
        logger.error("Failed to parse form data: %s", e)
        raise HTTPException(status_code=422, detail=f"Could not parse form fields: {e}")

    logger.info("Processing submission for: %s (%s)", form_data.name, form_data.email)

    # 2. Consent gate — reject if not checked
    if not form_data.consent:
        logger.warning("Submission rejected — no consent: %s", form_data.email)
        raise HTTPException(status_code=400, detail="Consent was not provided.")

    # 3. Download CV + Person Spec, call Claude, get the statement
    logger.info("Generating Supporting Information via Claude...")
    try:
        supporting_info = await generate_supporting_info(
            name=form_data.name,
            role=form_data.role,
            trust=form_data.trust,
            cv_url=form_data.cv_url,
            person_spec_url=form_data.person_spec_url,
            person_spec_filename=form_data.person_spec_filename,
        )
    except Exception as e:
        logger.error("Claude generation failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate Supporting Information: {e}",
        )

    logger.info("Supporting Information generated successfully.")

    # 4. Email the result to the applicant
    subject = f"Your Supporting Information — {form_data.role} at {form_data.trust}"
    email_body = (
        f"Dear {form_data.name},\n\n"
        f"Thank you for using the NHS Supporting Information Generator. "
        f"Below is your tailored statement for your application as "
        f"**{form_data.role}** at **{form_data.trust}**.\n\n"
        f"---\n\n"
        f"{supporting_info}\n\n"
        f"---\n\n"
        f"Please review and customise the statement as needed before "
        f"including it in your application.\n\n"
        f"Best of luck!\n\n"
        f"The NHS Supporting Information Generator"
    )

    logger.info("Sending email to %s...", form_data.email)
    try:
        await send_email(
            recipient=form_data.email,
            subject=subject,
            body=email_body,
        )
    except Exception as e:
        logger.error("Email sending failed: %s", e)
        raise HTTPException(
            status_code=500,
            detail=f"Supporting Information was generated but email delivery failed: {e}",
        )

    logger.info("Email sent successfully to %s", form_data.email)
    return {"status": "success", "message": "Supporting Information generated and sent."}
