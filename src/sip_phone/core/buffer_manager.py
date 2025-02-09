# src/sip_phone/core/buffer_manager.py
"""
Audio buffer management system.
Handles real-time audio buffering for both input and output streams,
providing thread-safe access to audio data with configurable buffer sizes.
"""

import asyncio
import logging
from typing import Optional, Deque
from collections import deque
import numpy as np

from ..utils.config import Config
from ..utils.errors import BufferError

logger = logging.getLogger(__name__)

class AudioBuffer:
    """
    Thread-safe circular buffer for audio data handling.
    Manages both raw audio data and processed samples with configurable sizes.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the audio buffer.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Buffer settings
        self.max_size = config.get('audio.buffer.max_size', 50)  # Maximum chunks
        self.chunk_size = config.get('audio.buffer.chunk_size', 160)  # 20ms @ 8kHz
        
        # Separate buffers for raw and processed audio
        self._raw_buffer: Deque[bytes] = deque(maxlen=self.max_size)
        self._processed_buffer: Deque[np.ndarray] = deque(maxlen=self.max_size)
        
        # Synchronization
        self._buffer_lock = asyncio.Lock()
        self._data_available = asyncio.Event()
        
        # Statistics
        self._overflow_count = 0
        self._underflow_count = 0
        
        logger.info(
            f"Initialized AudioBuffer with max_size={self.max_size}, "
            f"chunk_size={self.chunk_size}"
        )
        
    async def write_raw(self, audio_data: bytes) -> None:
        """
        Write raw audio data to the buffer.
        
        Args:
            audio_data: Raw audio data (G.711 encoded)
            
        Raises:
            BufferError: If buffer write fails
        """
        try:
            async with self._buffer_lock:
                if len(self._raw_buffer) >= self.max_size:
                    self._overflow_count += 1
                    if self._overflow_count % 100 == 0:
                        logger.warning(
                            f"Buffer overflow count: {self._overflow_count}"
                        )
                    return
                
                self._raw_buffer.append(audio_data)
                self._data_available.set()
                
        except Exception as e:
            logger.error(f"Error writing to raw buffer: {e}")
            raise BufferError(f"Failed to write to raw buffer: {e}")
            
    async def write_processed(self, samples: np.ndarray) -> None:
        """
        Write processed audio samples to the buffer.
        
        Args:
            samples: Processed audio samples as numpy array
            
        Raises:
            BufferError: If buffer write fails
        """
        try:
            async with self._buffer_lock:
                if len(self._processed_buffer) >= self.max_size:
                    self._overflow_count += 1
                    if self._overflow_count % 100 == 0:
                        logger.warning(
                            f"Buffer overflow count: {self._overflow_count}"
                        )
                    return
                
                self._processed_buffer.append(samples)
                self._data_available.set()
                
        except Exception as e:
            logger.error(f"Error writing to processed buffer: {e}")
            raise BufferError(f"Failed to write to processed buffer: {e}")
            
    async def read_raw(self, timeout: Optional[float] = 1.0) -> Optional[bytes]:
        """
        Read raw audio data from the buffer.
        
        Args:
            timeout: Maximum time to wait for data (seconds)
            
        Returns:
            Raw audio data or None if timeout
            
        Raises:
            BufferError: If buffer read fails
        """
        try:
            if not self._raw_buffer:
                if not await self._wait_for_data(timeout):
                    return None
                    
            async with self._buffer_lock:
                if not self._raw_buffer:
                    self._underflow_count += 1
                    if self._underflow_count % 100 == 0:
                        logger.warning(
                            f"Buffer underflow count: {self._underflow_count}"
                        )
                    return None
                    
                data = self._raw_buffer.popleft()
                if not self._raw_buffer:
                    self._data_available.clear()
                return data
                
        except Exception as e:
            logger.error(f"Error reading from raw buffer: {e}")
            raise BufferError(f"Failed to read from raw buffer: {e}")
            
    async def read_processed(
        self,
        timeout: Optional[float] = 1.0
    ) -> Optional[np.ndarray]:
        """
        Read processed audio samples from the buffer.
        
        Args:
            timeout: Maximum time to wait for data (seconds)
            
        Returns:
            Processed audio samples or None if timeout
            
        Raises:
            BufferError: If buffer read fails
        """
        try:
            if not self._processed_buffer:
                if not await self._wait_for_data(timeout):
                    return None
                    
            async with self._buffer_lock:
                if not self._processed_buffer:
                    self._underflow_count += 1
                    if self._underflow_count % 100 == 0:
                        logger.warning(
                            f"Buffer underflow count: {self._underflow_count}"
                        )
                    return None
                    
                samples = self._processed_buffer.popleft()
                if not self._processed_buffer:
                    self._data_available.clear()
                return samples
                
        except Exception as e:
            logger.error(f"Error reading from processed buffer: {e}")
            raise BufferError(f"Failed to read from processed buffer: {e}")
            
    async def _wait_for_data(self, timeout: Optional[float]) -> bool:
        """
        Wait for data to become available in the buffer.
        
        Args:
            timeout: Maximum time to wait (seconds)
            
        Returns:
            True if data available, False if timeout
        """
        try:
            if timeout is not None:
                return await asyncio.wait_for(
                    self._data_available.wait(),
                    timeout
                )
            else:
                await self._data_available.wait()
                return True
                
        except asyncio.TimeoutError:
            return False
            
    @property
    def raw_buffer_level(self) -> int:
        """Get current raw buffer fill level."""
        return len(self._raw_buffer)
        
    @property
    def processed_buffer_level(self) -> int:
        """Get current processed buffer fill level."""
        return len(self._processed_buffer)
        
    def clear(self) -> None:
        """Clear all buffers and reset statistics."""
        self._raw_buffer.clear()
        self._processed_buffer.clear()
        self._overflow_count = 0
        self._underflow_count = 0
        self._data_available.clear()
        logger.info("Audio buffers cleared")
