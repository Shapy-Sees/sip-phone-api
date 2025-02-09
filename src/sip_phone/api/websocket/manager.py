# src/sip_phone/api/websocket/manager.py
"""
This module provides WebSocket connection management for the SIP Phone API.
It coordinates different types of WebSocket connections and their lifecycles.
"""

import logging
import json
from datetime import datetime
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from .audio import audio_stream_manager
from ...core.state import PhoneState
from ...events.types import WebSocketEvent
from ...utils.config import Config
from ...utils.errors import WebSocketError

# Configure logging
logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections and message routing.
    Handles connection lifecycle and message distribution.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.control_connections: Set[WebSocket] = set()
        self.event_connections: Set[WebSocket] = set()
        self.client_info: Dict[WebSocket, dict] = {}
        self.allowed_api_keys = set(config.get('security.allowed_api_keys', []))
    
    async def connect(self, websocket: WebSocket, connection_type: str, api_key: Optional[str] = None):
        """
        Handle new WebSocket connection with authentication.
        
        Args:
            websocket: The WebSocket connection
            connection_type: Type of connection ('control', 'event', or 'audio')
            api_key: API key for authentication
            
        Raises:
            WebSocketException: If authentication fails
        """
        # Validate API key
        if not api_key or api_key not in self.allowed_api_keys:
            logger.warning("Rejected WebSocket connection: Invalid API key")
            await websocket.close(code=4001, reason="Invalid API key")
            return
            
        await websocket.accept()
        
        try:
            if connection_type == "audio":
                await audio_stream_manager.connect(websocket)
                return
                
            if connection_type == "control":
                self.control_connections.add(websocket)
                logger.info(f"New control connection. Active control connections: {len(self.control_connections)}")
            elif connection_type == "event":
                self.event_connections.add(websocket)
                logger.info(f"New event connection. Active event connections: {len(self.event_connections)}")
            else:
                logger.warning(f"Invalid connection type: {connection_type}")
                await websocket.close(code=4002, reason="Invalid connection type")
                return
                
            self.client_info[websocket] = {
                "type": connection_type,
                "authenticated": True,
                "connected_at": datetime.utcnow().isoformat()
            }
            
            # Send initial state
            await self.send_connection_status(websocket)
            
        except Exception as e:
            logger.error(f"Error establishing WebSocket connection: {str(e)}")
            await websocket.close(code=4000, reason="Internal server error")
            raise
    
    async def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection.
        """
        if websocket in self.control_connections:
            self.control_connections.remove(websocket)
            logger.info(f"Control connection closed. Active control connections: {len(self.control_connections)}")
        elif websocket in self.event_connections:
            self.event_connections.remove(websocket)
            logger.info(f"Event connection closed. Active event connections: {len(self.event_connections)}")
            
        self.client_info.pop(websocket, None)
    
    async def broadcast_event(self, event_type: str, data: dict):
        """
        Broadcast an event to all authenticated event listeners.
        """
        if not self.event_connections:
            return
            
        message = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        dead_connections = set()
        for connection in self.event_connections:
            try:
                await connection.send_json(message)
            except WebSocketDisconnect:
                dead_connections.add(connection)
            except Exception as e:
                logger.error(f"Error broadcasting event: {str(e)}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            await self.disconnect(connection)
    
    async def handle_control_message(self, websocket: WebSocket, message: dict):
        """
        Handle incoming control messages from authenticated clients.
        """
        try:
            # Verify authentication
            if not self.client_info.get(websocket, {}).get("authenticated"):
                await websocket.send_json({
                    "error": "Not authenticated",
                    "code": 4001
                })
                return
                
            command = message.get("command")
            if not command:
                await websocket.send_json({
                    "error": "Missing command in control message",
                    "code": 4003
                })
                return
                
            # Handle commands
            if command == "mute":
                await audio_stream_manager.mute()
                await self.broadcast_event("audio_state_changed", {"muted": True})
            elif command == "unmute":
                await audio_stream_manager.unmute()
                await self.broadcast_event("audio_state_changed", {"muted": False})
            elif command == "get_status":
                await self.send_connection_status(websocket)
            else:
                await websocket.send_json({
                    "error": f"Unknown command: {command}",
                    "code": 4004
                })
                
        except Exception as e:
            logger.error(f"Error handling control message: {str(e)}")
            await websocket.send_json({
                "error": f"Error processing command: {str(e)}"
            })
    
    async def handle_client_message(self, websocket: WebSocket):
        """
        Handle incoming messages from WebSocket clients.
        """
        try:
            connection_type = self.client_info.get(websocket, {}).get("type")
            
            if connection_type == "audio":
                await audio_stream_manager.handle_incoming_audio(websocket)
            elif connection_type == "control":
                message = await websocket.receive_json()
                await self.handle_control_message(websocket, message)
            else:
                # Event connections are read-only
                await websocket.send_json({
                    "error": "This connection type does not accept messages"
                })
                
        except WebSocketDisconnect:
            await self.disconnect(websocket)
        except Exception as e:
            logger.error(f"Error handling client message: {str(e)}")
            try:
                await websocket.send_json({
                    "error": f"Error processing message: {str(e)}"
                })
            except:
                await self.disconnect(websocket)

    async def send_connection_status(self, websocket: WebSocket):
        """
        Send current connection status to a client.
        
        Args:
            websocket: The WebSocket connection to send status to
        """
        try:
            client_info = self.client_info.get(websocket, {})
            status = {
                "type": "connection_status",
                "data": {
                    "connection_type": client_info.get("type"),
                    "authenticated": client_info.get("authenticated", False),
                    "connected_at": client_info.get("connected_at"),
                    "active_connections": {
                        "control": len(self.control_connections),
                        "event": len(self.event_connections),
                        "audio": audio_stream_manager.active_connections_count
                    }
                }
            }
            await websocket.send_json(status)
        except Exception as e:
            logger.error(f"Error sending connection status: {str(e)}")
            raise WebSocketError(f"Failed to send connection status: {str(e)}")

# Global connection manager instance
connection_manager = None

def init_connection_manager(config: Config) -> ConnectionManager:
    """Initialize the global connection manager with config."""
    global connection_manager
    if connection_manager is None:
        connection_manager = ConnectionManager(config)
    return connection_manager
