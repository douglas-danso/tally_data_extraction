"""Tally webhook endpoint with credit checking."""

import logging
import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from config import FRONTEND_URL
from database.session import get_db
from models import ParsedFormData, TallyWebhookPayload
from services import database_service
from services.claude_service import generate_supporting_info
from services.email_service import send_email, send_insufficient_credits_email
from services.tally_parser import extract_fields

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/webhook")
async def tally_webhook(
    payload: TallyWebhookPayload,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Receive a Tally submission, check credits, then process if available.

    Returns 200 immediately so Render's free-tier request timeout doesn't kill
    the connection while Claude is still generating the statement.
    """
    logger.info("Received submission for form: %s", payload.data.formName)

    # Parse and validate synchronously — fast, no external calls
    try:
        form_data = extract_fields(payload)
    except (KeyError, ValueError, IndexError) as e:
        logger.error("Failed to parse form data: %s", e)
        raise HTTPException(
            status_code=422, detail=f"Could not parse form fields: {e}"
        )

    logger.info("Submission received for: %s (%s)", form_data.name, form_data.email)

    if not form_data.consent:
        logger.warning("Submission rejected — no consent: %s", form_data.email)
        raise HTTPException(status_code=400, detail="Consent was not provided.")

    # Check if user has credits
    has_credits, available_credits = await database_service.check_user_credits(
        db, form_data.email
    )

    if not has_credits:
        logger.info(
            "User %s has insufficient credits (%d). Sending purchase email.",
            form_data.email,
            available_credits,
        )

        # Send email with checkout link
        background_tasks.add_task(
            send_insufficient_credits_email,
            recipient=form_data.email,
            name=form_data.name,
            checkout_url=f"{FRONTEND_URL}/packages",
        )

        return {
            "status": "insufficient_credits",
            "message": "You need to purchase credits first. Check your email for a link.",
        }

    # User has credits - process the submission
    logger.info(
        "User %s has credits (%s). Processing submission.",
        form_data.email,
        "unlimited" if available_credits == -1 else available_credits,
    )

    # Heavy work (downloads + Claude + email) runs after this response is sent
    background_tasks.add_task(process_submission_with_credit_deduction, form_data, db)

    return {
        "status": "accepted",
        "message": "Submission received. Processing in background.",
    }


async def process_submission_with_credit_deduction(
    form_data: ParsedFormData, db: AsyncSession
):
    """Download files, call Claude, email the result, and deduct credit.

    Runs as a background task.
    """
    logger.info(
        "Background: generating Supporting Information for %s...", form_data.name
    )

    # Get user to deduct credit later
    user = await database_service.get_user_by_email(db, form_data.email)
    if not user:
        logger.error("Background: User %s not found", form_data.email)
        return

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
        logger.error(
            "Background: Claude generation failed for %s: %s", form_data.email, e
        )
        return

    logger.info("Background: Supporting Information generated for %s.", form_data.name)

    # Deduct credit after successful generation
    try:
        await database_service.deduct_credit(db, user.id, credits=1)
        logger.info("Background: Deducted 1 credit from user %s", form_data.email)

        # Log usage for audit
        await database_service.log_credit_usage(
            db=db,
            user_id=user.id,
            credits_used=1,
            role=form_data.role,
            trust=form_data.trust,
            submission_id=str(uuid.uuid4()),  # Generate unique submission ID
        )
    except ValueError as e:
        logger.error("Background: Failed to deduct credit: %s", e)
        # Continue to send email even if credit deduction fails
        # (shouldn't happen since we checked credits earlier)

    # Send email with result
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
