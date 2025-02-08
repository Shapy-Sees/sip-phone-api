# src/sip_phone/api/websocket/manager.py
"""
This module provides WebSocket connection management for the SIP Phone API.
It coordinates different types of WebSocket connections and their lifecycles.
"""

import logging
import json
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from .audio import audio_stream_manager
from ...core.state import PhoneState
from ...events.types import WebSocketEvent

# Configure logging
logger = logging.getLogger(__name__)

class ConnectionManager:
    """
    Manages WebSocket connections and message routing.
    Handles connection lifecycle and message distribution.
    """
    
    def __init__(self):
        self.control_connections: Set[WebSocket] = set()
        self.event_connections: Set[WebSocket] = set()
        self.client_info: Dict[WebSocket, dict] = {}
    
    async def connect(self, websocket: WebSocket, connection_type: str):
        """
        Handle new WebSocket connection.
        
        Args:
            websocket: The WebSocket connection
            connection_type: Type of connection ('control', 'event', or 'audio')
        """
        await websocket.accept()
        
        if connection_type == "audio":
            await audio_stream_manager.connect(websocket)
            return
            
        if connection_type == "control":
            self.control_connections.add(websocket)
            logger.info(f"New control connection. Active control connections: {len(self.control_connections)}")
        elif connection_type == "event":
            self.event_connections.add(websocket)
            logger.info(f"New event connection. Active event connections: {len(self.event_connections)}")
            
        self.client_info[websocket] = {
            "type": connection_type,
            "authenticated": False  # TODO: Implement authentication
        }
    
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
        Broadcast an event to all connected event listeners.
        """
        if not self.event_connections:
            return
            
        message = {
            "type": event_type,
            "data": data
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
        Handle incoming control messages.
        """
        try:
            command = message.get("command")
            if not command:
                await websocket.send_json({
                    "error": "Missing command in control message"
                })
                return
                
            # TODO: Implement command handling
            if command == "mute":
                # Handle mute command
                pass
            elif command == "unmute":
                # Handle unmute command
                pass
            else:
                await websocket.send_json({
                    "error": f"Unknown command: {command}"
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

# Global connection manager instance
connection_manager = ConnectionManager()
