# src/sip_phone/api/models/phone.py
"""
This module defines the data models for phone-related API requests and responses.
These models provide type safety and validation for the API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict
from datetime import datetime
from enum import Enum

class PhoneState(str, Enum):
    """
    Enum representing possible phone states.
    """
    IDLE = "idle"
    RINGING = "ringing"
    CONNECTED = "connected"
    BUSY = "busy"
    ERROR = "error"

class RingRequest(BaseModel):
    """
    Model for triggering phone ring.
    """
    duration: Optional[int] = Field(30, description="Ring duration in seconds")
    pattern: Optional[str] = Field("standard", description="Ring pattern (standard/urgent/custom)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "duration": 30,
                "pattern": "standard"
            }
        }

class HangupRequest(BaseModel):
    """
    Model for ending a call.
    """
    force: Optional[bool] = Field(False, description="Force hangup even if in invalid state")
    
    class Config:
        json_schema_extra = {
            "example": {
                "force": False
            }
        }

class SystemStatus(BaseModel):
    """
    Model for system health and status information.
    """
    state: PhoneState = Field(..., description="Current phone state")
    uptime: int = Field(..., description="System uptime in seconds")
    memory_usage: float = Field(..., description="Memory usage percentage")
    cpu_usage: float = Field(..., description="CPU usage percentage")
    active_calls: int = Field(0, description="Number of active calls")
    errors: List[str] = Field(default_factory=list, description="Recent error messages")
    components: Dict[str, bool] = Field(..., description="Component status (sip/audio/etc)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "state": "idle",
                "uptime": 3600,
                "memory_usage": 45.2,
                "cpu_usage": 12.5,
                "active_calls": 0,
                "errors": [],
                "components": {
                    "sip_server": True,
                    "audio_processor": True,
                    "websocket": True
                }
            }
        }

class ErrorResponse(BaseModel):
    """
    Standardized error response model.
    """
    error: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    details: Optional[Dict] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "error": "Failed to initiate call",
                "code": "CALL_FAILED",
                "details": {
                    "reason": "Device busy",
                    "retry_after": 30
                },
                "timestamp": "2024-02-08T12:00:00Z"
            }
        }

class CallRequest(BaseModel):
    """
    Model for initiating a phone call.
    """
    number: str = Field(..., description="Phone number to call")
    caller_id: Optional[str] = Field(None, description="Caller ID to use for the call")
    timeout: Optional[int] = Field(30, description="Call timeout in seconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "number": "+1234567890",
                "caller_id": "John Doe",
                "timeout": 30
            }
        }

class DTMFRequest(BaseModel):
    """
    Model for sending DTMF tones.
    """
    digits: str = Field(..., description="DTMF digits to send (0-9, *, #)")
    duration: Optional[int] = Field(100, description="Duration of each tone in milliseconds")
    
    class Config:
        json_schema_extra = {
            "example": {
                "digits": "123*#",
                "duration": 100
            }
        }

class PhoneResponse(BaseModel):
    """
    Standard response model for phone operations.
    """
    status: str = Field(..., description="Operation status (success/error)")
    message: str = Field(..., description="Response message")
    error: Optional[str] = Field(None, description="Error details if status is error")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Call initiated successfully",
                "error": None,
                "timestamp": "2024-02-08T12:00:00Z"
            }
        }

class CallState(BaseModel):
    """
    Model representing the current state of a call.
    """
    call_id: str = Field(..., description="Unique identifier for the call")
    state: str = Field(..., description="Current call state (idle/ringing/connected/etc)")
    number: str = Field(..., description="Phone number associated with the call")
    start_time: Optional[datetime] = Field(None, description="Call start timestamp")
    duration: Optional[int] = Field(None, description="Call duration in seconds")
    muted: bool = Field(False, description="Whether the call is muted")
    dtmf_history: List[str] = Field(default_factory=list, description="History of DTMF tones sent")
    
    class Config:
        json_schema_extra = {
            "example": {
                "call_id": "call_123456",
                "state": "connected",
                "number": "+1234567890",
                "start_time": "2024-02-08T12:00:00Z",
                "duration": 120,
                "muted": False,
                "dtmf_history": ["1", "2", "3"]
            }
        }
