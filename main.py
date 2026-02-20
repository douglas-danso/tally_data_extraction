"""FastAPI application for NHS Supporting Information Generator with credit-based payments."""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import FRONTEND_URL
from routers import admin, packages, stripe_webhook, webhook

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="NHS Supporting Information Generator")

# =============================================================================
# CORS Configuration
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        FRONTEND_URL,
        "http://localhost:3000",  # Development
        "http://localhost:3001",
        "https://nhs-payment-frontend.vercel.app",
        "https://applysmartuk.uk" # Alternative dev port
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =============================================================================
# Include Routers
# =============================================================================

# Public webhook endpoint
app.include_router(webhook.router, tags=["webhook"])

# Stripe webhook
app.include_router(stripe_webhook.router, tags=["stripe"])

# Public packages API
app.include_router(packages.router)

# Admin API
app.include_router(admin.router)

# =============================================================================
# Health Check
# =============================================================================


@app.get("/health")
async def health():
    """Health check and db health endpoint."""
    # db = 
    return {"status": "ok"}


@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "service": "NHS Supporting Information Generator",
        "version": "2.0.0",
        "features": [
            "Credit-based payment system",
            "One-time credit packages",
            "Monthly subscriptions",
            "Admin dashboard",
        ],
    }
