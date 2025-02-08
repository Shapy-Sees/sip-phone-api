# src/sip_phone/api/models/webhooks.py
"""
This module defines the data models for webhook payloads and responses.
These models provide type safety and validation for webhook integrations.
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime

class BaseWebhook(BaseModel):
    """
    Base model for all webhook payloads.
    """
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Webhook timestamp")
    event_id: str = Field(..., description="Unique identifier for the webhook event")
    version: str = Field("1.0", description="Webhook payload version")

class DTMFWebhook(BaseWebhook):
    """
    Model for DTMF detection webhook payloads.
    """
    digits: str = Field(..., description="Detected DTMF digits")
    call_id: str = Field(..., description="ID of the call where DTMF was detected")
    duration: Optional[int] = Field(None, description="Duration of DTMF tone in milliseconds")
    confidence: Optional[float] = Field(None, description="DTMF detection confidence score")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_123456",
                "timestamp": "2024-02-08T12:00:00Z",
                "version": "1.0",
                "digits": "123",
                "call_id": "call_123456",
                "duration": 100,
                "confidence": 0.95
            }
        }

class StateChangeWebhook(BaseWebhook):
    """
    Model for phone state change webhook payloads.
    """
    previous_state: str = Field(..., description="Previous phone state")
    new_state: str = Field(..., description="New phone state")
    call_id: Optional[str] = Field(None, description="Associated call ID if applicable")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional state change metadata")
    
    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "evt_123456",
                "timestamp": "2024-02-08T12:00:00Z",
                "version": "1.0",
                "previous_state": "idle",
                "new_state": "ringing",
                "call_id": "call_123456",
                "metadata": {
                    "incoming": True,
                    "caller_number": "+1234567890"
                }
            }
        }

class WebhookResponse(BaseModel):
    """
    Standard response model for webhook processing results.
    """
    status: str = Field(..., description="Processing status (success/error)")
    message: str = Field(..., description="Response message")
    webhook_id: str = Field(..., description="ID of the processed webhook")
    processed_at: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Webhook processed successfully",
                "webhook_id": "evt_123456",
                "processed_at": "2024-02-08T12:00:00Z"
            }
        }

class WebhookError(BaseModel):
    """
    Model for webhook processing errors.
    """
    error_code: str = Field(..., description="Error code identifier")
    error_message: str = Field(..., description="Detailed error message")
    webhook_id: str = Field(..., description="ID of the failed webhook")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error_code": "INVALID_PAYLOAD",
                "error_message": "Invalid webhook payload format",
                "webhook_id": "evt_123456",
                "timestamp": "2024-02-08T12:00:00Z"
            }
        }
