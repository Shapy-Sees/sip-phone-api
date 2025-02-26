# src/sip_phone/events/handlers/__init__.py
"""
This module initializes the event handlers package and provides a central point
for registering event handlers with the event dispatcher.
"""

import logging
from typing import Optional

from ...utils.config import Config
from ..dispatcher import event_dispatcher
from ..types import EventType
from .webhook import webhook_handler, init_webhook_handler
from .websocket import websocket_handler

# Configure logging
logger = logging.getLogger(__name__)

async def init_handlers(config: Config) -> None:
    """
    Initialize all event handlers and register them with the event dispatcher.
    
    Args:
        config: Application configuration
    """
    try:
        # Initialize webhook handler
        handler = init_webhook_handler(config)
        await handler.start()
        
        # Register webhook handler for relevant events
        event_dispatcher.register_handler(
            handler.handle_event,
            [
                EventType.CALL_STARTED,
                EventType.CALL_ENDED,
                EventType.CALL_FAILED,
                EventType.CALL_CONNECTING,
                EventType.DTMF,
                EventType.STATE_CHANGE,
                EventType.SYSTEM_ERROR,
                EventType.SYSTEM_WARNING
            ]
        )
        
        # Register WebSocket handler for all events
        event_dispatcher.register_handler(
            websocket_handler.handle_event
        )
        
        logger.info("Event handlers initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize event handlers: {str(e)}")
        raise

async def cleanup_handlers() -> None:
    """
    Cleanup and shutdown all event handlers.
    """
    try:
        if webhook_handler:
            await webhook_handler.stop()
        logger.info("Event handlers cleaned up successfully")
    except Exception as e:
        logger.error(f"Error cleaning up event handlers: {str(e)}")

# Export handlers for direct access if needed
__all__ = [
    "init_handlers",
    "cleanup_handlers",
    "webhook_handler",
    "websocket_handler"
]
