# src/sip_phone/events/handlers/websocket.py
"""
This module implements the WebSocket event handler for the SIP Phone API.
It handles forwarding events to connected WebSocket clients based on their subscription type.
"""

import logging
import json
from typing import Dict, Set, Optional
from datetime import datetime

from ...api.websocket.manager import connection_manager
from ..types import (
    BaseEvent,
    EventType,
    CallEvent,
    DTMFEvent,
    StateEvent,
    AudioEvent
)

# Configure logging
logger = logging.getLogger(__name__)

class WebSocketEventHandler:
    """
    Handles forwarding events to connected WebSocket clients.
    Manages event filtering and client message formatting.
    """
    
    def __init__(self):
        # Event type mapping to determine which clients should receive which events
        self.event_mapping = {
            # Call events go to control and event connections
            EventType.CALL_INITIATED: {"control", "event"},
            EventType.CALL_CONNECTED: {"control", "event"},
            EventType.CALL_ENDED: {"control", "event"},
            EventType.CALL_FAILED: {"control", "event"},
            
            # DTMF events go to control and event connections
            EventType.DTMF_DETECTED: {"control", "event"},
            EventType.DTMF_SENT: {"control", "event"},
            
            # State changes go to all connection types
            EventType.STATE_CHANGED: {"control", "event", "audio"},
            
            # Audio events go to audio connections only
            EventType.AUDIO_STARTED: {"audio"},
            EventType.AUDIO_STOPPED: {"audio"},
            EventType.AUDIO_ERROR: {"audio"},
            
            # WebSocket events go to control connections only
            EventType.WS_CONNECTED: {"control"},
            EventType.WS_DISCONNECTED: {"control"},
            EventType.WS_ERROR: {"control"},
            
            # System events go to control and event connections
            EventType.SYSTEM_ERROR: {"control", "event"},
            EventType.SYSTEM_WARNING: {"control", "event"},
            EventType.SYSTEM_INFO: {"control", "event"}
        }
    
    def _prepare_event_message(self, event: BaseEvent) -> Dict:
        """
        Prepare an event for transmission over WebSocket.
        
        Args:
            event: The event to convert
            
        Returns:
            dict: The prepared WebSocket message
        """
        # Base message structure
        message = {
            "type": "event",
            "event_type": str(event.type),
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": event.event_id,
            "metadata": event.metadata
        }
        
        # Add event-specific data
        if isinstance(event, CallEvent):
            message["data"] = {
                "call_id": event.call_id,
                "phone_number": event.phone_number,
                "duration": event.duration,
                "error": event.error
            }
        elif isinstance(event, DTMFEvent):
            message["data"] = {
                "digits": event.digits,
                "call_id": event.call_id,
                "duration": event.duration,
                "confidence": event.confidence
            }
        elif isinstance(event, StateEvent):
            message["data"] = {
                "previous_state": event.previous_state,
                "new_state": event.new_state,
                "call_id": event.call_id,
                "reason": event.reason
            }
        elif isinstance(event, AudioEvent):
            message["data"] = {
                "stream_id": event.stream_id,
                "call_id": event.call_id,
                "error": event.error,
                "buffer_size": event.buffer_size
            }
        
        return message
    
    async def handle_event(self, event: BaseEvent) -> None:
        """
        Handle an event by forwarding it to appropriate WebSocket clients.
        
        Args:
            event: The event to handle
        """
        try:
            # Determine which connection types should receive this event
            target_types = self.event_mapping.get(event.type, set())
            if not target_types:
                logger.debug(f"No WebSocket clients configured for event type: {event.type}")
                return
            
            # Prepare the message once for all clients
            message = self._prepare_event_message(event)
            
            # Forward to control connections if needed
            if "control" in target_types:
                await connection_manager.broadcast_event(event.type, message)
            
            # Log the event distribution
            logger.debug(
                f"Event {event.type} forwarded to WebSocket clients: {target_types}"
            )
            
        except Exception as e:
            logger.error(f"Error handling WebSocket event: {str(e)}")

# Global WebSocket event handler instance
websocket_handler = WebSocketEventHandler()
