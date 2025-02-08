# src/sip_phone/core/sip_server.py
"""
Core SIP server implementation for Smart Home Phone Integration.
Uses python-sipsimple for SIP/RTP handling and built-in Python libraries for audio processing.
Provides WebSocket event notifications for client integration.
"""

import asyncio
import logging
from typing import Dict, Optional, Set, Callable
from datetime import datetime
from dataclasses import dataclass
import wave
import audioop
import array
from sipsimple.core import Engine, FromHeader, ToHeader, RouteHeader, SIPURI
from sipsimple.account import Account
from sipsimple.application import SIPApplication
from sipsimple.storage import MemoryStorage
from sipsimple.session import Session
from sipsimple.streams import AudioStream
from sipsimple.threading.green import run_in_green_thread

from ..utils.logger import DAHDILogger, log_function_call
from ..utils.config import Config

# Get structured logger
logger = DAHDILogger().get_logger(__name__)

@dataclass
class AudioConfig:
    """Audio configuration parameters"""
    sample_rate: int = 8000
    channels: int = 1
    bit_depth: int = 16
    ptime: int = 20  # Packet time in ms

class SIPServer(SIPApplication):
    """
    Core SIP server implementation using python-sipsimple.
    Handles SIP signaling, audio streaming, and phone state management.
    """
    def __init__(self):
        self.config = Config()
        self._setup_logging()
        
        # Initialize SIP engine
        SIPApplication.__init__(self)
        self.engine = Engine()
        self.storage = MemoryStorage()
        
        # Audio configuration
        self.audio_config = AudioConfig(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
            bit_depth=self.config.audio.bit_depth,
            ptime=self.config.audio.ptime
        )
        
        # State tracking
        self.phone_state = "on_hook"
        self.last_dtmf = None
        self.active_sessions: Dict[str, Session] = {}
        self.event_subscribers: Set[Callable] = set()
        
        logger.info("SIP server initialized")

    def _setup_logging(self) -> None:
        """Configure server-specific logging"""
        self.debug_stats = {
            'total_calls': 0,
            'active_calls': 0,
            'dtmf_events': 0,
            'audio_streams': 0
        }
        logger.debug("Server debug statistics initialized")

    @log_function_call(level="DEBUG")
    async def start(self) -> None:
        """Start SIP server and initialize resources"""
        try:
            # Start SIP engine
            self.engine.start()
            
            # Configure account
            self.account = Account(self.storage)
            self.account.sip.register = False  # We're a server
            self.account.auth.password = self.config.ht802.password
            self.account.save()
            
            # Start processing
            self.start(storage=self.storage)
            
            logger.info("SIP server started",
                       host=self.config.server.host,
                       port=self.config.server.sip_port)
            
        except Exception as e:
            logger.error("Failed to start SIP server", exc_info=True)
            raise

    async def stop(self) -> None:
        """Stop server and cleanup resources"""
        try:
            # End all sessions
            for session in self.active_sessions.values():
                session.end()
            
            # Stop SIP application
            self.stop()
            
            # Stop engine
            self.engine.stop()
            
            logger.info("SIP server stopped")
            
        except Exception as e:
            logger.error("Error stopping SIP server", exc_info=True)
            raise

    @run_in_green_thread
    def _handle_incoming_session(self, session: Session) -> None:
        """Handle incoming SIP session"""
        try:
            if str(session.remote_identity.uri) != self.config.ht802.host:
                logger.warning("Rejected session from unknown device",
                             source=session.remote_identity.uri)
                session.reject()
                return
                
            # Accept audio stream
            audio_stream = session.proposed_streams[0]
            session.accept([audio_stream])
            
            # Store session
            session_id = str(session.call_id)
            self.active_sessions[session_id] = session
            
            # Update state
            self.phone_state = "off_hook"
            self.debug_stats['total_calls'] += 1
            self.debug_stats['active_calls'] += 1
            
            # Notify subscribers
            asyncio.create_task(self._notify_subscribers({
                "type": "off_hook",
                "timestamp": datetime.utcnow().isoformat()
            }))
            
            logger.info("Call established", session_id=session_id)
            
        except Exception as e:
            logger.error("Error handling incoming session", exc_info=True)

    def _handle_dtmf(self, session: Session, digit: str, duration: int) -> None:
        """Handle DTMF digit"""
        try:
            # Update state
            self.last_dtmf = digit
            self.debug_stats['dtmf_events'] += 1
            
            # Notify subscribers
            asyncio.create_task(self._notify_subscribers({
                "type": "dtmf",
                "digit": digit,
                "timestamp": datetime.utcnow().isoformat()
            }))
            
            logger.info("DTMF received", digit=digit)
            
        except Exception as e:
            logger.error("Error handling DTMF", exc_info=True)

    def _handle_audio(self, session: Session, audio_data: bytes) -> None:
        """Handle audio data"""
        try:
            # Convert audio if needed
            if self.audio_config.bit_depth == 16:
                # Convert PCMU/PCMA to PCM
                audio_data = audioop.ulaw2lin(audio_data, 2)
            
            # Process audio (example: level detection)
            max_sample = max(array.array('h', audio_data))
            if max_sample > 8000:  # Voice activity threshold
                logger.debug("Voice activity detected", level=max_sample)
            
            # Forward audio to subscribers if needed
            # This would integrate with your smart home system
            
        except Exception as e:
            logger.error("Error handling audio", exc_info=True)

    async def subscribe_events(self, callback: Callable) -> None:
        """Subscribe to phone events"""
        self.event_subscribers.add(callback)
        logger.debug("Event subscriber added",
                    total_subscribers=len(self.event_subscribers))

    async def unsubscribe_events(self, callback: Callable) -> None:
        """Unsubscribe from phone events"""
        self.event_subscribers.discard(callback)
        logger.debug("Event subscriber removed",
                    total_subscribers=len(self.event_subscribers))

    async def _notify_subscribers(self, event: dict) -> None:
        """Notify all event subscribers"""
        for callback in self.event_subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error("Error notifying subscriber", exc_info=True)

    @run_in_green_thread
    def ring(self, duration: int = 2000) -> None:
        """Trigger phone to ring"""
        try:
            # Create session for ring
            uri = SIPURI(host=self.config.ht802.host)
            session = Session(self.account)
            audio_stream = AudioStream()
            session.connect([audio_stream], uri)
            
            # Wait for duration
            from threading import Event
            timer = Event()
            timer.wait(duration / 1000)
            
            # End session
            session.end()
            
            logger.info("Ring completed", duration=duration)
            
        except Exception as e:
            logger.error("Error triggering ring", exc_info=True)
            raise

    async def get_state(self) -> dict:
        """Get current phone state"""
        return {
            "state": self.phone_state,
            "last_dtmf": self.last_dtmf,
            "active_calls": len(self.active_sessions),
            "stats": self.debug_stats
        }

# Example usage:
"""
server = SIPServer()
await server.start()

# Subscribe to events
async def handle_event(event):
    print(f"Event received: {event}")
await server.subscribe_events(handle_event)

# Ring the phone
await server.ring(2000)  # 2 second ring

# Get current state
state = await server.get_state()
print(f"Current state: {state}")

# Cleanup
await server.stop()
"""