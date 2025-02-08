# src/sip_phone/integrations/operator/models.py
"""
This module defines data models for operator server communication.
These models provide type safety and validation for API requests and responses.
"""

from pydantic import BaseModel, Field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum

class OperatorStatus(BaseModel):
    """
    Model representing operator server status.
    """
    status: str = Field(..., description="Current server status (online/offline/degraded)")
    version: str = Field(..., description="Server version")
    uptime: int = Field(..., description="Server uptime in seconds")
    active_calls: int = Field(..., description="Number of active calls")
    total_calls: int = Field(..., description="Total calls handled")
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "online",
                "version": "1.0.0",
                "uptime": 3600,
                "active_calls": 5,
                "total_calls": 1000
            }
        }

class RouteType(str, Enum):
    """
    Enumeration of possible call routing types.
    """
    DIRECT = "direct"
    QUEUE = "queue"
    IVR = "ivr"
    CONFERENCE = "conference"
    VOICEMAIL = "voicemail"

class RouteRequest(BaseModel):
    """
    Model for call routing requests.
    """
    phone_number: str = Field(..., description="Phone number to route")
    caller_id: Optional[str] = Field(None, description="Caller ID if available")
    call_type: str = Field(..., description="Type of call (inbound/outbound)")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Request timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional routing metadata"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "phone_number": "+1234567890",
                "caller_id": "John Doe",
                "call_type": "inbound",
                "timestamp": "2024-02-08T12:00:00Z",
                "metadata": {
                    "department": "sales",
                    "priority": "high"
                }
            }
        }

class RouteResponse(BaseModel):
    """
    Model for call routing responses.
    """
    route_type: RouteType = Field(..., description="Type of routing to perform")
    destination: str = Field(..., description="Routing destination")
    priority: int = Field(default=0, description="Routing priority")
    timeout: int = Field(default=30, description="Routing timeout in seconds")
    fallback: Optional[str] = Field(None, description="Fallback destination")
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional routing parameters"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "route_type": "queue",
                "destination": "sales_queue",
                "priority": 1,
                "timeout": 30,
                "fallback": "voicemail",
                "parameters": {
                    "queue_position": 1,
                    "estimated_wait": 120
                }
            }
        }

class CallState(str, Enum):
    """
    Enumeration of possible call states.
    """
    INITIATED = "initiated"
    RINGING = "ringing"
    CONNECTED = "connected"
    ENDED = "ended"
    FAILED = "failed"

class CallRequest(BaseModel):
    """
    Model for call notifications to operator.
    """
    call_id: str = Field(..., description="Unique call identifier")
    phone_number: str = Field(..., description="Phone number involved")
    direction: str = Field(..., description="Call direction (inbound/outbound)")
    state: CallState = Field(..., description="Current call state")
    start_time: datetime = Field(
        default_factory=datetime.utcnow,
        description="Call start timestamp"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional call metadata"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "call_id": "call_123456",
                "phone_number": "+1234567890",
                "direction": "inbound",
                "state": "connected",
                "start_time": "2024-02-08T12:00:00Z",
                "metadata": {
                    "caller_name": "John Doe",
                    "department": "sales"
                }
            }
        }

class CallResponse(BaseModel):
    """
    Model for operator responses to call notifications.
    """
    success: bool = Field(..., description="Whether the operation succeeded")
    message: str = Field(..., description="Response message")
    call_id: str = Field(..., description="Call identifier")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow,
        description="Response timestamp"
    )
    actions: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Actions to take for the call"
    )
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Call notification processed",
                "call_id": "call_123456",
                "timestamp": "2024-02-08T12:00:00Z",
                "actions": [
                    {
                        "type": "record",
                        "enabled": True
                    },
                    {
                        "type": "monitor",
                        "supervisor": "supervisor_1"
                    }
                ]
            }
        }

# Export all models
__all__ = [
    "OperatorStatus",
    "RouteType",
    "RouteRequest",
    "RouteResponse",
    "CallState",
    "CallRequest",
    "CallResponse"
]
