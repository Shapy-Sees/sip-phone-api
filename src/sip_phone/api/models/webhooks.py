# src/sip_phone/api/models/webhooks.py
"""
This module defines the data models for webhook payloads and responses.
These models provide type safety and validation for webhook integrations.

The models enforce proper data structure and validation for all incoming
webhooks and outgoing responses, ensuring consistency across the API.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from ...events.types import CallState

class WebhookType(str, Enum):
    """
    Enum for different types of webhooks.
    """
    DTMF = "dtmf"
    STATE_CHANGE = "state_change"
    OPERATOR = "operator"
    CUSTOM = "custom"

class BaseWebhook(BaseModel):
    """
    Base model for all webhook payloads.
    """
    timestamp: Optional[datetime] = Field(default_factory=datetime.utcnow, description="Webhook timestamp")
    event_id: Optional[str] = Field(None, description="Unique identifier for the webhook event")
    version: str = Field("1.0", description="Webhook payload version")
    webhook_type: WebhookType = Field(..., description="Type of webhook")

class DTMFWebhook(BaseWebhook):
    """
    Model for DTMF detection webhook payloads.
    """
    digits: str = Field(..., description="Detected DTMF digits", regex="^[0-9*#]+$")
    call_id: str = Field(..., description="ID of the call where DTMF was detected")
    duration: Optional[int] = Field(100, description="Duration of DTMF tone in milliseconds", ge=50, le=1000)
    confidence: Optional[float] = Field(None, description="DTMF detection confidence score", ge=0.0, le=1.0)
    
    @validator('digits')
    def validate_digits(cls, v):
        if not 1 <= len(v) <= 32:
            raise ValueError("DTMF sequence must be between 1 and 32 digits")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "webhook_type": "dtmf",
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
    previous_state: CallState = Field(..., description="Previous phone state")
    new_state: CallState = Field(..., description="New phone state")
    call_id: Optional[str] = Field(None, description="Associated call ID if applicable")
    reason: Optional[str] = Field(None, description="Reason for state change")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional state change metadata")

    @validator('new_state')
    def validate_state_transition(cls, v, values):
        from ...core.state_manager import StateManager
        if 'previous_state' in values:
            if v not in StateManager.VALID_TRANSITIONS.get(values['previous_state'], set()):
                raise ValueError(f"Invalid state transition: {values['previous_state']} -> {v}")
        return v
    
    class Config:
        json_schema_extra = {
            "example": {
                "webhook_type": "state_change",
                "event_id": "evt_123456",
                "timestamp": "2024-02-08T12:00:00Z",
                "version": "1.0",
                "previous_state": "on_hook",
                "new_state": "ringing",
                "call_id": "call_123456",
                "reason": "incoming_call",
                "metadata": {
                    "incoming": True,
                    "caller_number": "+1234567890"
                }
            }
        }

class OperatorAction(str, Enum):
    """
    Enum for valid operator actions.
    """
    HANGUP = "hangup"
    MUTE = "mute"
    UNMUTE = "unmute"
    HOLD = "hold"
    RESUME = "resume"

class OperatorWebhook(BaseWebhook):
    """
    Model for operator service webhook payloads.
    """
    action: OperatorAction = Field(..., description="Action to perform")
    call_id: str = Field(..., description="ID of the call to act on")
    params: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional action parameters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "webhook_type": "operator",
                "event_id": "evt_123456",
                "timestamp": "2024-02-08T12:00:00Z",
                "version": "1.0",
                "action": "mute",
                "call_id": "call_123456",
                "params": {
                    "duration": 30
                }
            }
        }

class WebhookResponse(BaseModel):
    """
    Standard response model for webhook processing results.
    """
    status: str = Field(..., description="Processing status (success/error)")
    message: str = Field(..., description="Response message")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Processing timestamp")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional response details")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Webhook processed successfully",
                "timestamp": "2024-02-08T12:00:00Z",
                "details": {
                    "event_id": "evt_123456",
                    "action_taken": "state_updated"
                }
            }
        }

class WebhookError(BaseModel):
    """
    Model for webhook processing errors.
    """
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code identifier")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Error timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Invalid webhook payload",
                "code": "INVALID_PAYLOAD",
                "details": {
                    "field": "action",
                    "reason": "Invalid operator action"
                },
                "timestamp": "2024-02-08T12:00:00Z"
            }
        }

class CustomWebhookPayload(BaseModel):
    """
    Model for custom integration webhook payloads.
    """
    integration: str = Field(..., description="Name of the integration")
    action: str = Field(..., description="Action to perform")
    update_state: Optional[CallState] = Field(None, description="New state to transition to")
    params: Dict[str, Any] = Field(default_factory=dict, description="Action parameters")
    
    class Config:
        json_schema_extra = {
            "example": {
                "integration": "home_assistant",
                "action": "door_opened",
                "update_state": "ringing",
                "params": {
                    "door_id": "front_door",
                    "trigger_time": "2024-02-08T12:00:00Z"
                }
            }
        }
