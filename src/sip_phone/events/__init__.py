# src/sip_phone/events/__init__.py
"""
This module initializes the events package and provides a central point for accessing
the event system functionality. It exposes the event types, dispatcher, and handlers
for use throughout the application.
"""

import logging
from typing import Optional

from .types import (
    EventType,
    BaseEvent,
    CallEvent,
    DTMFEvent,
    StateEvent,
    AudioEvent,
    WebSocketEvent,
    WebhookEvent,
    SystemEvent
)
from .dispatcher import event_dispatcher
from .handlers import (
    init_handlers,
    cleanup_handlers,
    webhook_handler,
    websocket_handler
)

# Configure logging
logger = logging.getLogger(__name__)

async def init_event_system(config) -> None:
    """
    Initialize the event system, including the dispatcher and all handlers.
    
    Args:
        config: Application configuration
    """
    try:
        # Start event dispatcher
        await event_dispatcher.start()
        
        # Initialize handlers
        await init_handlers(config)
        
        logger.info("Event system initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize event system: {str(e)}")
        raise

async def shutdown_event_system() -> None:
    """
    Shutdown the event system and cleanup resources.
    """
    try:
        # Cleanup handlers
        await cleanup_handlers()
        
        # Stop event dispatcher
        await event_dispatcher.stop()
        
        logger.info("Event system shutdown successfully")
    except Exception as e:
        logger.error(f"Error shutting down event system: {str(e)}")

# Export all event-related components
__all__ = [
    # Event types
    "EventType",
    "BaseEvent",
    "CallEvent",
    "DTMFEvent",
    "StateEvent",
    "AudioEvent",
    "WebSocketEvent",
    "WebhookEvent",
    "SystemEvent",
    
    # Event system components
    "event_dispatcher",
    "webhook_handler",
    "websocket_handler",
    
    # System management
    "init_event_system",
    "shutdown_event_system"
]
