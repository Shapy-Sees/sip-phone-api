# src/sip_phone/api/websocket/audio.py
"""
This module handles WebSocket-based audio streaming for the SIP Phone API.
It manages real-time audio transmission between the phone and connected clients.
"""

import logging
import asyncio
from datetime import datetime
from typing import Dict, Set, Optional, Any
from fastapi import WebSocket, WebSocketDisconnect
from ...core.state import PhoneState
from ...core.dtmf import DTMFDetector
from ...core.audio_processor import AudioProcessor
from ...utils.config import Config
from ...utils.errors import WebSocketError
from .manager import connection_manager

# Configure logging
logger = logging.getLogger(__name__)

class AudioStreamManager:
    """
    Manages WebSocket connections for audio streaming.
    Handles bidirectional audio transmission and processing.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.active_connections: Set[WebSocket] = set()
        self.audio_processor = AudioProcessor(config)
        self.dtmf_detector = DTMFDetector()
        self.stream_task: Optional[asyncio.Task] = None
        self.muted = False
        self.stats: Dict[str, Any] = {
            "processed_frames": 0,
            "dropped_frames": 0,
            "last_error": None,
            "last_error_time": None
        }
        
    async def connect(self, websocket: WebSocket):
        """
        Handle new WebSocket connection for audio streaming.
        """
        try:
            self.active_connections.add(websocket)
            logger.info(f"New audio WebSocket connection established. Active connections: {len(self.active_connections)}")
            
            # Start audio processor if not running
            if not self.audio_processor._running:
                await self.audio_processor.start()
            
            # Start streaming task if not running
            if not self.stream_task:
                self.stream_task = asyncio.create_task(self._stream_audio())
                
            # Register WebSocket as stream handler
            self.audio_processor.add_stream_handler(
                f"ws_{id(websocket)}", 
                lambda data: self._handle_processed_audio(websocket, data)
            )
            
        except Exception as e:
            logger.error(f"Error establishing audio connection: {str(e)}")
            self.stats["last_error"] = str(e)
            self.stats["last_error_time"] = datetime.utcnow().isoformat()
            raise WebSocketError(f"Failed to establish audio connection: {str(e)}")
    
    async def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection.
        """
        self.active_connections.remove(websocket)
        logger.info(f"Audio WebSocket connection closed. Active connections: {len(self.active_connections)}")
        
        if not self.active_connections and self.stream_task:
            self.stream_task.cancel()
            self.stream_task = None
    
    async def broadcast_audio(self, audio_data: bytes):
        """
        Broadcast audio data to all connected clients.
        """
        if not self.active_connections:
            return
            
        dead_connections = set()
        for connection in self.active_connections:
            try:
                await connection.send_bytes(audio_data)
            except WebSocketDisconnect:
                dead_connections.add(connection)
            except Exception as e:
                logger.error(f"Error broadcasting audio: {str(e)}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            await self.disconnect(connection)
    
    async def _stream_audio(self):
        """
        Main audio streaming loop.
        Reads from audio processor and broadcasts to connected clients.
        """
        logger.info("Starting audio streaming loop")
        try:
            while self.active_connections:
                try:
                    # Get processed audio from processor
                    audio_data = await self.audio_processor.get_next_frame()
                    if audio_data and not self.muted:
                        # Process for DTMF
                        if self.dtmf_detector.process_audio(audio_data):
                            digits = self.dtmf_detector.get_detected_digits()
                            if digits:
                                logger.info(f"DTMF detected: {digits}")
                                await self._handle_dtmf(digits)
                        
                        # Broadcast to clients
                        await self.broadcast_audio(audio_data)
                        self.stats["processed_frames"] += 1
                    else:
                        await asyncio.sleep(0.01)  # Prevent tight loop
                        
                except Exception as e:
                    logger.error(f"Error processing audio frame: {str(e)}")
                    self.stats["dropped_frames"] += 1
                    self.stats["last_error"] = str(e)
                    self.stats["last_error_time"] = datetime.utcnow().isoformat()
                    await asyncio.sleep(0.1)  # Back off on error
                    
        except asyncio.CancelledError:
            logger.info("Audio streaming loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in audio streaming loop: {str(e)}")
            self.stats["last_error"] = str(e)
            self.stats["last_error_time"] = datetime.utcnow().isoformat()
        finally:
            logger.info("Audio streaming loop ended")
            await self.audio_processor.stop()
    
    async def handle_incoming_audio(self, websocket: WebSocket):
        """
        Handle incoming audio from a WebSocket connection.
        """
        try:
            while True:
                try:
                    audio_data = await websocket.receive_bytes()
                    if not self.muted:
                        # Process incoming audio
                        processed = await self.audio_processor.process_frame(
                            audio_data,
                            f"ws_{id(websocket)}"
                        )
                        if processed:
                            self.stats["processed_frames"] += 1
                except WebSocketDisconnect:
                    logger.info("Client disconnected from audio stream")
                    break
                except Exception as e:
                    logger.error(f"Error handling incoming audio: {str(e)}")
                    self.stats["dropped_frames"] += 1
                    self.stats["last_error"] = str(e)
                    self.stats["last_error_time"] = datetime.utcnow().isoformat()
                    await asyncio.sleep(0.1)  # Back off on error
                    
        finally:
            await self.disconnect(websocket)
            
    async def mute(self):
        """Mute audio streaming."""
        self.muted = True
        logger.info("Audio stream muted")
        
    async def unmute(self):
        """Unmute audio streaming."""
        self.muted = False
        logger.info("Audio stream unmuted")
        
    async def _handle_dtmf(self, digits: str):
        """Handle detected DTMF digits."""
        try:
            # Trigger DTMF event
            event_data = {
                "digits": digits,
                "timestamp": datetime.utcnow().isoformat(),
                "call_id": "current"  # TODO: Get from state manager
            }
            await connection_manager.broadcast_event("dtmf_detected", event_data)
        except Exception as e:
            logger.error(f"Error handling DTMF event: {str(e)}")
            
    async def _handle_processed_audio(self, websocket: WebSocket, audio_data: bytes):
        """Handle processed audio data for a specific WebSocket."""
        try:
            if not self.muted and websocket in self.active_connections:
                await websocket.send_bytes(audio_data)
        except Exception as e:
            logger.error(f"Error sending processed audio: {str(e)}")
            await self.disconnect(websocket)
            
    @property
    def active_connections_count(self) -> int:
        """Get the number of active audio connections."""
        return len(self.active_connections)

# Global audio stream manager instance
audio_stream_manager = None

def init_audio_stream_manager(config: Config) -> AudioStreamManager:
    """Initialize the global audio stream manager with config."""
    global audio_stream_manager
    if audio_stream_manager is None:
        audio_stream_manager = AudioStreamManager(config)
    return audio_stream_manager
