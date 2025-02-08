# src/sip_phone/core/dtmf.py
"""
DTMF detection and processing module.
Handles real-time DTMF tone detection from audio stream and processes the detected tones.
"""

import logging
import asyncio
from typing import Optional, Callable
import numpy as np
from scipy.signal import butter, lfilter

from ..utils.config import Config
from ..utils.errors import DtmfError, AudioError
from ..integrations.webhooks import WebhookManager

logger = logging.getLogger(__name__)

# DTMF frequencies (Hz)
DTMF_FREQS = {
    'row': [697, 770, 852, 941],
    'col': [1209, 1336, 1477, 1633]
}

# DTMF digit mapping
DTMF_DIGITS = [
    ['1', '2', '3', 'A'],
    ['4', '5', '6', 'B'],
    ['7', '8', '9', 'C'],
    ['*', '0', '#', 'D']
]

class DtmfProcessor:
    """Handles DTMF detection and processing from audio stream."""
    
    def __init__(self, config: Config, webhook_manager: WebhookManager):
        """
        Initialize the DTMF processor.
        
        Args:
            config: Application configuration
            webhook_manager: WebhookManager instance for dispatching DTMF events
        """
        self.config = config
        self.webhook_manager = webhook_manager
        self.sample_rate = 8000  # Standard for G.711
        self.frame_size = 160    # 20ms at 8kHz
        self.detection_threshold = 0.4
        self.min_duration_ms = 40
        self._current_digit: Optional[str] = None
        self._digit_start_time: Optional[float] = None
        self._running = False
        
    async def start(self):
        """Start the DTMF processor."""
        self._running = True
        logger.info("DTMF processor started")
        
    async def stop(self):
        """Stop the DTMF processor."""
        self._running = False
        logger.info("DTMF processor stopped")
        
    def process_audio(self, audio_data: bytes, call_id: str):
        """
        Process incoming audio data for DTMF detection.
        
        Args:
            audio_data: Raw audio data (G.711 encoded)
            call_id: Current call identifier
        """
        try:
            # Convert G.711 to PCM samples
            samples = self._decode_g711(audio_data)
            
            # Detect DTMF tones
            digit = self._detect_dtmf(samples)
            
            if digit:
                current_time = asyncio.get_event_loop().time()
                
                # New digit detected
                if self._current_digit != digit:
                    if self._current_digit:
                        # End previous digit
                        self._handle_digit_end(call_id, current_time)
                    
                    # Start new digit
                    self._current_digit = digit
                    self._digit_start_time = current_time
                    logger.debug(f"DTMF digit {digit} started")
                    
            elif self._current_digit:
                # End of digit detection
                self._handle_digit_end(call_id, current_time)
                
        except Exception as e:
            logger.error(f"Error processing audio for DTMF: {e}")
            raise AudioError(f"DTMF processing failed: {e}")
            
    def _handle_digit_end(self, call_id: str, end_time: float):
        """Handle the end of a detected DTMF digit."""
        if not self._digit_start_time:
            return
            
        duration_ms = int((end_time - self._digit_start_time) * 1000)
        
        if duration_ms >= self.min_duration_ms:
            # Dispatch webhook for valid DTMF digit
            asyncio.create_task(
                self.webhook_manager.dispatch_dtmf(
                    self._current_digit,
                    call_id,
                    duration_ms
                )
            )
            logger.info(
                f"DTMF digit {self._current_digit} ended "
                f"(duration: {duration_ms}ms)"
            )
            
        self._current_digit = None
        self._digit_start_time = None
        
    def _detect_dtmf(self, samples: np.ndarray) -> Optional[str]:
        """
        Detect DTMF tones in audio samples using Goertzel algorithm.
        
        Args:
            samples: Audio samples as numpy array
            
        Returns:
            Detected DTMF digit or None
        """
        if len(samples) < self.frame_size:
            return None
            
        # Calculate energies at DTMF frequencies
        row_energies = [
            self._goertzel(samples, freq, self.sample_rate)
            for freq in DTMF_FREQS['row']
        ]
        col_energies = [
            self._goertzel(samples, freq, self.sample_rate)
            for freq in DTMF_FREQS['col']
        ]
        
        # Find strongest frequencies
        row_idx = np.argmax(row_energies)
        col_idx = np.argmax(col_energies)
        
        # Check if energies exceed threshold
        if (row_energies[row_idx] > self.detection_threshold and
            col_energies[col_idx] > self.detection_threshold):
            return DTMF_DIGITS[row_idx][col_idx]
            
        return None
        
    def _goertzel(self, samples: np.ndarray, freq: float, sample_rate: int) -> float:
        """
        Goertzel algorithm for efficient frequency detection.
        
        Args:
            samples: Audio samples
            freq: Target frequency
            sample_rate: Audio sample rate
            
        Returns:
            Energy at target frequency
        """
        n = len(samples)
        k = int(0.5 + n * freq / sample_rate)
        w = 2 * np.pi * k / n
        cosw = np.cos(w)
        sinw = np.sin(w)
        
        # Initialize coefficients
        coeff = 2 * cosw
        s0, s1, s2 = 0.0, 0.0, 0.0
        
        # Process samples
        for sample in samples:
            s0 = sample + coeff * s1 - s2
            s2 = s1
            s1 = s0
            
        # Calculate energy
        return np.sqrt(s1 * s1 + s2 * s2 - coeff * s1 * s2)
        
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
        
        # μ-law decoding table (pre-computed for efficiency)
        decoded = self._ulaw_to_pcm(encoded)
        
        return decoded
        
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
