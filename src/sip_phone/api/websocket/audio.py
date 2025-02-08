# src/sip_phone/api/websocket/audio.py
"""
This module handles WebSocket-based audio streaming for the SIP Phone API.
It manages real-time audio transmission between the phone and connected clients.
"""

import logging
import asyncio
from typing import Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from ...core.state import PhoneState
from ...core.dtmf import DTMFDetector
from ...hardware.ht802 import AudioBuffer

# Configure logging
logger = logging.getLogger(__name__)

class AudioStreamManager:
    """
    Manages WebSocket connections for audio streaming.
    Handles bidirectional audio transmission and processing.
    """
    
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.audio_buffer = AudioBuffer()
        self.dtmf_detector = DTMFDetector()
        self.stream_task: Optional[asyncio.Task] = None
        
    async def connect(self, websocket: WebSocket):
        """
        Handle new WebSocket connection for audio streaming.
        """
        await websocket.accept()
        self.active_connections.add(websocket)
        logger.info(f"New audio WebSocket connection established. Active connections: {len(self.active_connections)}")
        
        if not self.stream_task:
            self.stream_task = asyncio.create_task(self._stream_audio())
    
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
        Reads from audio buffer and broadcasts to connected clients.
        """
        logger.info("Starting audio streaming loop")
        try:
            while self.active_connections:
                audio_chunk = await self.audio_buffer.read()
                if audio_chunk:
                    # Process audio for DTMF detection
                    if self.dtmf_detector.process_audio(audio_chunk):
                        digits = self.dtmf_detector.get_detected_digits()
                        if digits:
                            logger.info(f"DTMF detected: {digits}")
                            # TODO: Trigger DTMF event handling
                    
                    # Broadcast processed audio
                    await self.broadcast_audio(audio_chunk)
                else:
                    await asyncio.sleep(0.01)  # Prevent tight loop when no audio
        except asyncio.CancelledError:
            logger.info("Audio streaming loop cancelled")
        except Exception as e:
            logger.error(f"Error in audio streaming loop: {str(e)}")
        finally:
            logger.info("Audio streaming loop ended")
    
    async def handle_incoming_audio(self, websocket: WebSocket):
        """
        Handle incoming audio from a WebSocket connection.
        """
        try:
            while True:
                audio_data = await websocket.receive_bytes()
                # TODO: Process incoming audio (e.g., for call recording)
                await self.audio_buffer.write(audio_data)
        except WebSocketDisconnect:
            logger.info("Client disconnected from audio stream")
        except Exception as e:
            logger.error(f"Error handling incoming audio: {str(e)}")
        finally:
            await self.disconnect(websocket)

# Global audio stream manager instance
audio_stream_manager = AudioStreamManager()
