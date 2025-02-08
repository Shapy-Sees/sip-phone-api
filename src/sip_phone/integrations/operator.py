# src/sip_phone/integrations/operator.py
"""
Operator server communication module that handles WebSocket-based audio streaming
and state synchronization with the remote operator server.
"""

import logging
import asyncio
import websockets
from typing import Optional, Callable
from dataclasses import dataclass

from ..utils.config import Config
from ..utils.errors import OperatorConnectionError

logger = logging.getLogger(__name__)

@dataclass
class AudioStreamConfig:
    """Configuration for audio streaming."""
    url: str
    buffer_size: int = 0  # Direct forwarding by default
    compression: str = "none"

class OperatorClient:
    def __init__(self, config: Config):
        self.config = config
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.audio_config = self._load_audio_config()
        self._state_callback: Optional[Callable] = None
        self._reconnect_task: Optional[asyncio.Task] = None
        self._running = False

    def _load_audio_config(self) -> AudioStreamConfig:
        """Load audio streaming configuration from config file."""
        audio_config = self.config.get("audio.websocket", {})
        return AudioStreamConfig(
            url=audio_config.get("url", ""),
            buffer_size=audio_config.get("buffer_size", 0),
            compression=audio_config.get("compression", "none")
        )

    async def start(self, state_callback: Optional[Callable] = None):
        """
        Start the operator client and establish WebSocket connection.
        
        Args:
            state_callback: Optional callback for receiving state updates
        """
        self._running = True
        self._state_callback = state_callback
        self._reconnect_task = asyncio.create_task(self._connection_manager())
        logger.info("Operator client started")

    async def stop(self):
        """Gracefully stop the operator client."""
        self._running = False
        if self._reconnect_task:
            self._reconnect_task.cancel()
        if self.websocket:
            await self.websocket.close()
        logger.info("Operator client stopped")

    async def _connection_manager(self):
        """Manage WebSocket connection with automatic reconnection."""
        while self._running:
            try:
                if not self.websocket or self.websocket.closed:
                    self.websocket = await websockets.connect(
                        self.audio_config.url,
                        ping_interval=20,
                        ping_timeout=10
                    )
                    logger.info("Connected to operator server")
                    asyncio.create_task(self._handle_messages())

                await asyncio.sleep(1)  # Check connection periodically

            except Exception as e:
                logger.error(f"Operator connection error: {e}")
                await asyncio.sleep(5)  # Wait before retry

    async def _handle_messages(self):
        """Handle incoming WebSocket messages."""
        if not self.websocket:
            return

        try:
            async for message in self.websocket:
                if isinstance(message, str):
                    # Handle state updates
                    if self._state_callback:
                        await self._state_callback(message)
                else:
                    # Binary messages not expected from operator
                    logger.warning("Received unexpected binary message from operator")

        except websockets.ConnectionClosed:
            logger.info("Operator connection closed")
        except Exception as e:
            logger.error(f"Error handling operator messages: {e}")

    async def stream_audio(self, audio_data: bytes):
        """
        Stream audio data to the operator server.
        
        Args:
            audio_data: Raw audio data to stream
        """
        if not self.websocket or self.websocket.closed:
            raise OperatorConnectionError("Not connected to operator server")

        try:
            await self.websocket.send(audio_data)
        except Exception as e:
            logger.error(f"Error streaming audio: {e}")
            raise OperatorConnectionError(f"Audio streaming failed: {e}")

    async def send_state_update(self, state: dict):
        """
        Send state update to operator server.
        
        Args:
            state: State data to send
        """
        if not self.websocket or self.websocket.closed:
            raise OperatorConnectionError("Not connected to operator server")

        try:
            await self.websocket.send(str(state))
            logger.debug(f"Sent state update: {state}")
        except Exception as e:
            logger.error(f"Error sending state update: {e}")
            raise OperatorConnectionError(f"State update failed: {e}")
