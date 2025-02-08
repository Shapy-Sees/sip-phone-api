# src/sip_phone/api/websocket/__init__.py
"""
This module initializes the WebSocket package and provides the main WebSocket endpoints
for the SIP Phone API. It exposes connection handlers for different types of WebSocket
connections (audio, control, and events).
"""

import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Optional

from .audio import audio_stream_manager
from .manager import connection_manager

# Configure logging
logger = logging.getLogger(__name__)

# Create router for WebSocket endpoints
router = APIRouter()

@router.websocket("/ws/{connection_type}")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_type: str = Query(..., regex="^(audio|control|event)$"),
    client_id: Optional[str] = None
):
    """
    Main WebSocket endpoint that handles different types of connections.
    
    Args:
        websocket: The WebSocket connection
        connection_type: Type of connection ('audio', 'control', or 'event')
        client_id: Optional client identifier
    """
    logger.info(f"New WebSocket connection request: type={connection_type}, client_id={client_id}")
    
    try:
        # Initialize connection based on type
        await connection_manager.connect(websocket, connection_type)
        
        # Handle messages based on connection type
        while True:
            await connection_manager.handle_client_message(websocket)
            
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected: type={connection_type}, client_id={client_id}")
        await connection_manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {str(e)}")
        await connection_manager.disconnect(websocket)

# Export key components
__all__ = [
    "router",
    "connection_manager",
    "audio_stream_manager"
]
