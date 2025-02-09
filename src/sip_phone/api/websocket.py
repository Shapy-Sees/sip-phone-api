# src/sip_phone/api/websocket.py
"""
WebSocket routes for the SIP Phone API.
Handles WebSocket connections for real-time audio streaming and event notifications.
"""

import logging
from typing import Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Header, Request
from ..utils.errors import WebSocketError

# Configure logging
logger = logging.getLogger(__name__)

# Create router
router = APIRouter()

@router.websocket("/ws/{connection_type}")
async def websocket_endpoint(
    websocket: WebSocket,
    connection_type: str,
    request: Request,
    x_api_key: Optional[str] = Header(None)
):
    """
    WebSocket endpoint for real-time communication.
    
    Args:
        websocket: The WebSocket connection
        connection_type: Type of connection ('control', 'event', or 'audio')
        request: The FastAPI request object
        x_api_key: API key for authentication
    """
    try:
        # Validate connection type
        if connection_type not in ["control", "event", "audio"]:
            await websocket.close(code=4002, reason="Invalid connection type")
            return
            
        # Get managers from app state
        connection_manager = request.app.state.connection_manager
        audio_manager = request.app.state.audio_manager
        
        try:
            # Connect with authentication
            await connection_manager.connect(websocket, connection_type, x_api_key)
            
            # Handle messages until disconnect
            while True:
                try:
                    await connection_manager.handle_client_message(websocket)
                except WebSocketDisconnect:
                    logger.info(f"WebSocket disconnected: {connection_type}")
                    break
                    
        except WebSocketError as e:
            logger.warning(f"WebSocket error: {str(e)}")
            if not websocket.client_state.disconnected:
                await websocket.close(code=4000, reason=str(e))
        except Exception as e:
            logger.error(f"Unexpected error in WebSocket handler: {str(e)}")
            if not websocket.client_state.disconnected:
                await websocket.close(code=4000, reason="Internal server error")
        finally:
            # Clean up connection
            await connection_manager.disconnect(websocket)
            
    except Exception as e:
        logger.error(f"Fatal error in WebSocket endpoint: {str(e)}")
        if not websocket.client_state.disconnected:
            await websocket.close(code=4000, reason="Internal server error")

@router.get("/ws/status")
async def websocket_status(request: Request):
    """Get current WebSocket connection status."""
    try:
        connection_manager = request.app.state.connection_manager
        audio_manager = request.app.state.audio_manager
        
        return {
            "connections": {
                "control": len(connection_manager.control_connections),
                "event": len(connection_manager.event_connections),
                "audio": audio_manager.active_connections_count
            },
            "audio_stats": audio_manager.stats
        }
    except Exception as e:
        logger.error(f"Error getting WebSocket status: {str(e)}")
        raise WebSocketError(f"Failed to get WebSocket status: {str(e)}")
