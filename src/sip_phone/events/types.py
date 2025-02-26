# src/sip_phone/events/types.py
"""
This module defines event types and structures used throughout the SIP Phone API.
These events represent various system occurrences that can be handled by event handlers.
"""

from enum import Enum
from typing import Dict, Any, Optional, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class CallState(str, Enum):
    """
    Enumeration of possible call states.
    """
    ON_HOOK = "on_hook"
    OFF_HOOK = "off_hook"
    RINGING = "ringing"
    CONNECTING = "connecting"
    ACTIVE = "active"
    ENDED = "ended"
    ERROR = "error"

class EventType(str, Enum):
    """
    Enumeration of possible event types in the system.
    """
    # Call-related events
    CALL_STARTED = "call_started"
    CALL_ENDED = "call_ended"
    CALL_FAILED = "call_failed"
    CALL_CONNECTING = "call_connecting"
    
    # DTMF events
    DTMF = "dtmf"
    
    # Audio events
    AUDIO_DATA = "audio_data"
    AUDIO_ERROR = "audio_error"
    AUDIO_LEVEL = "audio_level"
    
    # State events
    STATE_CHANGE = "state_change"
    REGISTRATION = "registration"
    
    # System events
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_INFO = "system_info"

class BaseEvent(BaseModel):
    """
    Base model for all events in the system.
    """
    event_id: str = Field(..., description="Unique identifier for the event")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class CallEvent(BaseEvent):
    """
    Event model for call-related events.
    """
    call_id: str
    phone_number: str
    duration: Optional[int] = None
    error: Optional[str] = None

class DTMFEvent(BaseEvent):
    """
    Event model for DTMF-related events.
    """
    type: Literal["dtmf"] = "dtmf"
    digit: str
    call_id: str
    duration: int
    sequence: int
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())

class PhoneEvent(BaseEvent):
    """
    Event model for phone-related events (calls, audio, state changes).
    """
    type: Literal["call_started", "call_ended", "call_connecting", "audio_data", "audio_level", "registration"]
    call_id: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    remote_uri: Optional[str] = None
    data: Optional[bytes] = None  # For audio data

class WebSocketEvent(BaseEvent):
    """
    Event model for WebSocket-related events.
    """
    connection_id: str
    connection_type: str
    client_id: Optional[str] = None
    error: Optional[str] = None

class WebhookEvent(BaseEvent):
    """
    Event model for webhook-related events.
    """
    webhook_id: str
    source: str
    payload: Dict[str, Any]
    error: Optional[str] = None

class StateEvent(BaseEvent):
    """
    Event model for state change events.
    """
    previous_state: CallState
    new_state: CallState
    call_id: Optional[str] = None
    reason: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class SystemEvent(BaseEvent):
    """
    Event model for system-level events.
    """
    level: str  # 'error', 'warning', 'info'
    component: str
    message: str
    error: Optional[str] = None
    stack_trace: Optional[str] = None

# Type aliases for event handlers
EventHandler = callable[[BaseEvent], None]
AsyncEventHandler = callable[[BaseEvent], Any]  # Returns a coroutine

# Export all event types
__all__ = [
    "CallState",
    "EventType",
    "BaseEvent",
    "CallEvent",
    "DTMFEvent",
    "PhoneEvent",
    "WebSocketEvent",
    "WebhookEvent",
    "StateEvent",
    "SystemEvent",
    "EventHandler",
    "AsyncEventHandler"
]
