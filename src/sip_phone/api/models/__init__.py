# src/sip_phone/api/models/__init__.py
"""
This module initializes the API models package and re-exports commonly used models
for easier importing throughout the application.
"""

from .phone import (
    CallRequest,
    DTMFRequest,
    PhoneResponse,
    CallState
)

from .webhooks import (
    BaseWebhook,
    DTMFWebhook,
    StateChangeWebhook,
    WebhookResponse,
    WebhookError
)

__all__ = [
    # Phone models
    "CallRequest",
    "DTMFRequest",
    "PhoneResponse",
    "CallState",
    
    # Webhook models
    "BaseWebhook",
    "DTMFWebhook",
    "StateChangeWebhook",
    "WebhookResponse",
    "WebhookError"
]
