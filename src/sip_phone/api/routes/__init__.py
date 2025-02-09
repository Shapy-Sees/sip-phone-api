# src/sip_phone/api/routes/__init__.py
"""
This module initializes the API routes package and provides route registration functionality.
It serves as the central point for organizing and exposing all API endpoints.
"""

from fastapi import APIRouter
from . import phone, status, webhooks
from .. import websocket

# Create main router
router = APIRouter()

# Include all route modules
router.include_router(phone.router, prefix="/phone", tags=["phone"])
router.include_router(status.router, prefix="/status", tags=["status"])
router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
router.include_router(websocket.router, tags=["websocket"])

__all__ = ["router"]
