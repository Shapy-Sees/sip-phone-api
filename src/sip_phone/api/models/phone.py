# src/sip_phone/api/models/phone.py
"""
This module defines the data models for phone-related API requests and responses.
These models provide type safety and validation for the API endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

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
