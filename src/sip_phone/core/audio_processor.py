# src/sip_phone/core/audio_processor.py
"""
Audio processing system for SIP phone implementation.
Handles real-time audio processing, including G.711 decoding/encoding,
buffer management, and DTMF detection.
"""

import asyncio
import logging
from typing import Optional, Callable, Dict
import numpy as np
from scipy import signal

from ..utils.config import Config
from ..utils.errors import AudioError
from .buffer_manager import AudioBuffer
from .dtmf import DtmfProcessor

logger = logging.getLogger(__name__)

class AudioProcessor:
    """
    Handles real-time audio processing for the SIP phone system.
    Manages audio streams, processing pipeline, and integration with other components.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the audio processor.
        
        Args:
            config: Application configuration
        """
        self.config = config
        
        # Audio settings
        self.sample_rate = config.get('audio.sample_rate', 8000)  # Hz
        self.frame_size = config.get('audio.frame_size', 160)    # samples (20ms @ 8kHz)
        self.channels = config.get('audio.channels', 1)          # mono
        
        # Initialize components
        self.buffer = AudioBuffer(config)
        self.dtmf = DtmfProcessor(config, None)  # webhook manager set later
        
        # Processing pipeline configuration
        self.gain = config.get('audio.gain', 1.0)
        self.enable_agc = config.get('audio.agc.enabled', True)
        self.agc_target = config.get('audio.agc.target_level', -18)  # dB
        self.enable_noise_reduction = config.get('audio.noise_reduction', True)
        
        # Runtime state
        self._running = False
        self._processing_task: Optional[asyncio.Task] = None
        self._stream_handlers: Dict[str, Callable] = {}
        
        # Statistics
        self._processed_frames = 0
        self._dropped_frames = 0
        self._last_level = 0
        
        logger.info(
            f"Initialized AudioProcessor (sample_rate={self.sample_rate}Hz, "
            f"frame_size={self.frame_size})"
        )
        
    async def start(self):
        """Start the audio processor."""
        if self._running:
            return
            
        self._running = True
        self._processing_task = asyncio.create_task(self._processing_loop())
        logger.info("Audio processor started")
        
    async def stop(self):
        """Stop the audio processor."""
        if not self._running:
            return
            
        self._running = False
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
            self._processing_task = None
            
        self.buffer.clear()
        logger.info("Audio processor stopped")
        
    async def process_frame(self, audio_data: bytes, call_id: str) -> Optional[bytes]:
        """
        Process a single frame of audio data.
        
        Args:
            audio_data: Raw G.711 audio data
            call_id: Current call identifier
            
        Returns:
            Processed audio data (G.711 encoded) or None if processing fails
            
        Raises:
            AudioError: If audio processing fails
        """
        try:
            # Decode G.711 to PCM samples
            samples = self._decode_g711(audio_data)
            
            # Apply processing pipeline
            processed = await self._apply_processing(samples)
            
            # Check for DTMF
            self.dtmf.process_audio(audio_data, call_id)
            
            # Update level statistics
            self._update_statistics(processed)
            
            # Encode back to G.711
            return self._encode_g711(processed)
            
        except Exception as e:
            logger.error(f"Error processing audio frame: {e}")
            self._dropped_frames += 1
            raise AudioError(f"Frame processing failed: {e}")
            
    async def _processing_loop(self):
        """Main audio processing loop."""
        logger.info("Starting audio processing loop")
        try:
            while self._running:
                # Read from input buffer
                raw_data = await self.buffer.read_raw(timeout=0.1)
                if not raw_data:
                    continue
                    
                # Process audio
                try:
                    processed = await self.process_frame(raw_data, "default")
                    if processed:
                        # Write to output buffer
                        await self.buffer.write_processed(processed)
                        self._processed_frames += 1
                except Exception as e:
                    logger.error(f"Error in processing loop: {e}")
                    self._dropped_frames += 1
                    continue
                    
                # Notify handlers
                for handler in self._stream_handlers.values():
                    try:
                        await handler(processed)
                    except Exception as e:
                        logger.error(f"Error in stream handler: {e}")
                        
        except asyncio.CancelledError:
            logger.info("Audio processing loop cancelled")
        except Exception as e:
            logger.error(f"Fatal error in processing loop: {e}")
        finally:
            logger.info(
                f"Audio processing loop ended (processed={self._processed_frames}, "
                f"dropped={self._dropped_frames})"
            )
            
    async def _apply_processing(self, samples: np.ndarray) -> np.ndarray:
        """
        Apply audio processing pipeline to samples.
        
        Args:
            samples: Input audio samples
            
        Returns:
            Processed audio samples
        """
        # Apply gain
        samples = samples * self.gain
        
        # Automatic Gain Control (AGC)
        if self.enable_agc:
            level = 20 * np.log10(np.abs(samples).mean() + 1e-10)
            gain_adjust = self.agc_target - level
            samples = samples * (10 ** (gain_adjust / 20))
            
        # Noise reduction
        if self.enable_noise_reduction:
            # Simple noise gate
            noise_floor = np.abs(samples).mean() * 0.1
            samples[np.abs(samples) < noise_floor] = 0
            
        # Ensure we don't clip
        samples = np.clip(samples, -1.0, 1.0)
        
        return samples
        
    def _decode_g711(self, audio_data: bytes) -> np.ndarray:
        """
        Decode G.711 μ-law audio data to PCM samples.
        
        Args:
            audio_data: Raw G.711 audio data
            
        Returns:
            Numpy array of PCM samples
        """
        # Convert bytes to unsigned integers
        encoded = np.frombuffer(audio_data, dtype=np.uint8)
        
        # μ-law decoding
        decoded = self._ulaw_to_pcm(encoded)
        
        return decoded
        
    def _encode_g711(self, samples: np.ndarray) -> bytes:
        """
        Encode PCM samples to G.711 μ-law format.
        
        Args:
            samples: Audio samples to encode
            
        Returns:
            G.711 encoded audio data
        """
        # Scale to 16-bit range
        samples = (samples * 32768).astype(np.int16)
        
        # μ-law encoding
        encoded = self._pcm_to_ulaw(samples)
        
        return encoded.tobytes()
        
    def _ulaw_to_pcm(self, encoded: np.ndarray) -> np.ndarray:
        """
        Convert μ-law values to PCM samples.
        
        Args:
            encoded: Array of μ-law values
            
        Returns:
            Array of PCM samples
        """
        # Flip bits
        encoded = ~encoded
        
        # Extract sign and magnitude
        sign = 1 - 2 * (encoded >> 7)
        mantissa = encoded & 0x0F
        exponent = (encoded >> 4) & 0x07
        
        # Decode to 16-bit PCM
        decoded = sign * (mantissa * 2 ** (exponent + 3) + 2 ** (exponent + 3) - 33)
        
        return decoded.astype(np.float32) / 32768.0  # Normalize to [-1, 1]
        
    def _pcm_to_ulaw(self, samples: np.ndarray) -> np.ndarray:
        """
        Convert PCM samples to μ-law values.
        
        Args:
            samples: Array of PCM samples
            
        Returns:
            Array of μ-law values
        """
        # Extract sign and magnitude
        sign = (samples < 0).astype(np.uint8)
        samples = np.abs(samples)
        
        # Add bias and clip
        samples = np.clip(samples + 132, 0, 32767)
        
        # Calculate exponent and mantissa
        exponent = (np.log2(samples) - 6).astype(np.uint8)
        exponent = np.clip(exponent, 0, 7)
        mantissa = ((samples >> (exponent + 3)) & 0x0F).astype(np.uint8)
        
        # Combine fields and flip bits
        return ~(sign << 7 | exponent << 4 | mantissa)
        
    def _update_statistics(self, samples: np.ndarray):
        """Update audio level statistics."""
        self._last_level = 20 * np.log10(np.abs(samples).mean() + 1e-10)
        
    def add_stream_handler(self, handler_id: str, handler: Callable):
        """
        Add a handler for processed audio streams.
        
        Args:
            handler_id: Unique handler identifier
            handler: Async callback function for handling processed audio
        """
        self._stream_handlers[handler_id] = handler
        logger.info(f"Added stream handler: {handler_id}")
        
    def remove_stream_handler(self, handler_id: str):
        """
        Remove a stream handler.
        
        Args:
            handler_id: Handler identifier to remove
        """
        if handler_id in self._stream_handlers:
            del self._stream_handlers[handler_id]
            logger.info(f"Removed stream handler: {handler_id}")
            
    @property
    def stats(self) -> dict:
        """Get current audio processing statistics."""
        return {
            'processed_frames': self._processed_frames,
            'dropped_frames': self._dropped_frames,
            'buffer_level': self.buffer.raw_buffer_level,
            'last_level_db': self._last_level,
        }
