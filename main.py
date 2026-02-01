import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException

from models import ParsedFormData, TallyWebhookPayload
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
async def tally_webhook(payload: TallyWebhookPayload, background_tasks: BackgroundTasks):
    """Receive a Tally submission, validate it, then kick off processing in the background.

    Returns 200 immediately so Render's free-tier request timeout doesn't kill
    the connection while Claude is still generating the statement.
    """
    logger.info("Received submission for form: %s", payload.data.formName)

    # Parse and validate synchronously — fast, no external calls
    try:
        form_data = extract_fields(payload)
    except (KeyError, ValueError, IndexError) as e:
        logger.error("Failed to parse form data: %s", e)
        raise HTTPException(status_code=422, detail=f"Could not parse form fields: {e}")

    logger.info("Submission received for: %s (%s)", form_data.name, form_data.email)

    if not form_data.consent:
        logger.warning("Submission rejected — no consent: %s", form_data.email)
        raise HTTPException(status_code=400, detail="Consent was not provided.")

    # Heavy work (downloads + Claude + email) runs after this response is sent
    background_tasks.add_task(process_submission, form_data)

    return {"status": "accepted", "message": "Submission received. Processing in background."}


async def process_submission(form_data: ParsedFormData):
    """Download files, call Claude, email the result. Runs as a background task."""
    logger.info("Background: generating Supporting Information for %s...", form_data.name)

    try:
        supporting_info = await generate_supporting_info(
            name=form_data.name,
            role=form_data.role,
            trust=form_data.trust,
            cv_url=form_data.cv_url,
            person_spec_url=form_data.person_spec_url,
            person_spec_mimetype=form_data.person_spec_mimetype,
        )
    except Exception as e:
        logger.error("Background: Claude generation failed for %s: %s", form_data.email, e)
        return

    logger.info("Background: Supporting Information generated for %s.", form_data.name)

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

    try:
        await send_email(
            recipient=form_data.email,
            subject=subject,
            body=email_body,
        )
        logger.info("Background: email sent successfully to %s.", form_data.email)
    except Exception as e:
        logger.error("Background: email failed for %s: %s", form_data.email, e)
