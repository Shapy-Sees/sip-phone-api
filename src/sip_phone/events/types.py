# src/sip_phone/events/types.py
"""
This module defines event types and structures used throughout the SIP Phone API.
These events represent various system occurrences that can be handled by event handlers.
"""

from enum import Enum
from typing import Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class EventType(str, Enum):
    """
    Enumeration of possible event types in the system.
    """
    # Call-related events
    CALL_INITIATED = "call_initiated"
    CALL_CONNECTED = "call_connected"
    CALL_ENDED = "call_ended"
    CALL_FAILED = "call_failed"
    
    # DTMF events
    DTMF_DETECTED = "dtmf_detected"
    DTMF_SENT = "dtmf_sent"
    
    # State change events
    STATE_CHANGED = "state_changed"
    
    # Audio events
    AUDIO_STARTED = "audio_started"
    AUDIO_STOPPED = "audio_stopped"
    AUDIO_ERROR = "audio_error"
    
    # WebSocket events
    WS_CONNECTED = "ws_connected"
    WS_DISCONNECTED = "ws_disconnected"
    WS_ERROR = "ws_error"
    
    # Webhook events
    WEBHOOK_RECEIVED = "webhook_received"
    WEBHOOK_PROCESSED = "webhook_processed"
    WEBHOOK_FAILED = "webhook_failed"
    
    # System events
    SYSTEM_ERROR = "system_error"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_INFO = "system_info"

class BaseEvent(BaseModel):
    """
    Base model for all events in the system.
    """
    type: EventType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    event_id: str = Field(..., description="Unique identifier for the event")
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
    digits: str
    call_id: str
    duration: Optional[int] = None
    confidence: Optional[float] = None

class StateEvent(BaseEvent):
    """
    Event model for state change events.
    """
    previous_state: str
    new_state: str
    call_id: Optional[str] = None
    reason: Optional[str] = None

class AudioEvent(BaseEvent):
    """
    Event model for audio-related events.
    """
    stream_id: str
    call_id: Optional[str] = None
    error: Optional[str] = None
    buffer_size: Optional[int] = None

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
    "EventType",
    "BaseEvent",
    "CallEvent",
    "DTMFEvent",
    "StateEvent",
    "AudioEvent",
    "WebSocketEvent",
    "WebhookEvent",
    "SystemEvent",
    "EventHandler",
    "AsyncEventHandler"
]
