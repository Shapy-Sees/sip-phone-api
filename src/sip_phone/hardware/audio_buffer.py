# src/dahdi_phone/hardware/audio_buffer.py
"""
Audio buffer implementation for DAHDI phone system.
Provides thread-safe circular buffer for audio data with overflow protection,
supporting both blocking and non-blocking operations. Includes comprehensive
logging and monitoring capabilities.
"""

import threading
import collections
from typing import Optional, Tuple
import numpy as np
import logging
from ..utils.logger import DAHDILogger, log_function_call

# Configure module logger
logger = DAHDILogger().get_logger(__name__)

class AudioBufferError(Exception):
    """Custom exception for audio buffer operations"""
    pass

class AudioBuffer:
    """
    Thread-safe circular audio buffer with monitoring.
    Handles audio data buffering with configurable overflow behavior.
    """
    def __init__(self, 
                 max_size_bytes: int,
                 channels: int = 1,
                 sample_width: int = 2,  # 16-bit audio
                 overflow_strategy: str = 'drop'):
        """
        Initialize audio buffer.
        
        Args:
            max_size_bytes: Maximum buffer size in bytes
            channels: Number of audio channels
            sample_width: Bytes per sample
            overflow_strategy: How to handle overflow ('drop' or 'overwrite')
        """
        self.max_size = max_size_bytes
        self.channels = channels
        self.sample_width = sample_width
        self.overflow_strategy = overflow_strategy
        
        # Calculate derived values
        self.samples_per_frame = max_size_bytes // (channels * sample_width)
        
        # Initialize buffer and synchronization
        self._buffer = collections.deque(maxlen=self.samples_per_frame)
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._not_full = threading.Condition(self._lock)
        
        # Initialize statistics
        self.stats = {
            'total_writes': 0,
            'total_reads': 0,
            'overflows': 0,
            'underflows': 0,
            'dropped_samples': 0
        }
        
        logger.info(
            "audio_buffer_initialized",
            max_size=max_size_bytes,
            channels=channels,
            sample_width=sample_width,
            samples_per_frame=self.samples_per_frame
        )

    @property
    def available_samples(self) -> int:
        """Number of samples available to read"""
        with self._lock:
            return len(self._buffer)

    @property
    def free_space(self) -> int:
        """Number of samples that can be written"""
        with self._lock:
            return self._buffer.maxlen - len(self._buffer)

    @log_function_call(level="DEBUG")
    async def write(self, 
                   data: bytes,
                   timeout: Optional[float] = None) -> Tuple[int, int]:
        """
        Write audio data to buffer.
        
        Args:
            data: Audio data bytes
            timeout: Optional write timeout in seconds
            
        Returns:
            Tuple of (samples written, samples dropped)
            
        Raises:
            AudioBufferError: If write operation fails
        """
        try:
            # Convert bytes to samples
            samples = np.frombuffer(data, dtype=np.int16)
            samples_to_write = len(samples)
            dropped = 0
            
            with self._lock:
                if len(self._buffer) + samples_to_write > self._buffer.maxlen:
                    if self.overflow_strategy == 'drop':
                        dropped = samples_to_write
                        self.stats['dropped_samples'] += dropped
                        self.stats['overflows'] += 1
                        logger.warning(
                            "buffer_overflow_dropped",
                            dropped_samples=dropped,
                            total_dropped=self.stats['dropped_samples']
                        )
                        return 0, dropped
                    else:  # overwrite
                        # Remove old samples to make room
                        to_remove = len(self._buffer) + samples_to_write - self._buffer.maxlen
                        for _ in range(to_remove):
                            self._buffer.popleft()
                        dropped = to_remove
                        self.stats['dropped_samples'] += dropped
                        self.stats['overflows'] += 1
                        logger.warning(
                            "buffer_overflow_overwrote",
                            overwritten_samples=dropped,
                            total_dropped=self.stats['dropped_samples']
                        )
                
                # Write new samples
                self._buffer.extend(samples)
                self.stats['total_writes'] += 1
                
                # Notify readers
                self._not_empty.notify()
                
                logger.debug(
                    "audio_data_written",
                    samples_written=samples_to_write,
                    samples_dropped=dropped,
                    buffer_utilization=len(self._buffer)/self._buffer.maxlen
                )
                
                return samples_to_write, dropped
                
        except Exception as e:
            logger.error(
                "write_failed",
                error=str(e),
                data_size=len(data),
                exc_info=True
            )
            raise AudioBufferError(f"Buffer write failed: {str(e)}") from e

    @log_function_call(level="DEBUG")
    async def read(self,
                  samples: int,
                  timeout: Optional[float] = None) -> Optional[bytes]:
        """
        Read audio samples from buffer.
        
        Args:
            samples: Number of samples to read
            timeout: Optional read timeout in seconds
            
        Returns:
            Audio data bytes or None if not enough data
            
        Raises:
            AudioBufferError: If read operation fails
        """
        try:
            with self._lock:
                if len(self._buffer) < samples:
                    self.stats['underflows'] += 1
                    logger.warning(
                        "buffer_underflow",
                        requested_samples=samples,
                        available_samples=len(self._buffer)
                    )
                    return None
                
                # Read requested samples
                result = []
                for _ in range(samples):
                    result.append(self._buffer.popleft())
                
                self.stats['total_reads'] += 1
                
                # Notify writers
                self._not_full.notify()
                
                # Convert to bytes
                audio_data = np.array(result, dtype=np.int16).tobytes()
                
                logger.debug(
                    "audio_data_read",
                    samples_read=samples,
                    buffer_utilization=len(self._buffer)/self._buffer.maxlen
                )
                
                return audio_data
                
        except Exception as e:
            logger.error(
                "read_failed",
                error=str(e),
                requested_samples=samples,
                exc_info=True
            )
            raise AudioBufferError(f"Buffer read failed: {str(e)}") from e

    async def clear(self) -> None:
        """Clear buffer contents"""
        with self._lock:
            self._buffer.clear()
            self._not_full.notify_all()
            logger.info("buffer_cleared")

    async def get_stats(self) -> dict:
        """Get buffer statistics"""
        with self._lock:
            stats = {
                **self.stats,
                'current_utilization': len(self._buffer) / self._buffer.maxlen,
                'available_samples': len(self._buffer),
                'free_space': self.free_space
            }
            logger.debug("stats_retrieved", stats=stats)
            return stats