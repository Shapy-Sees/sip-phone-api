# src/sip_phone/core/sip_server.py
"""
Core SIP server implementation for Smart Home Phone Integration.
Uses python-sipsimple for SIP/RTP handling and built-in Python libraries for audio processing.
Provides WebSocket event notifications for client integration.

This server handles:
- SIP signaling (REGISTER, INVITE, BYE)
- RTP audio stream management
- Call state tracking
- Event dispatching
- Comprehensive logging for debugging
"""

import asyncio
import logging
from typing import Dict, Optional, Set, Callable, Any
from datetime import datetime
from dataclasses import dataclass
import wave
import audioop
import array
import uuid
from sipsimple.core import (
    Engine, FromHeader, ToHeader, RouteHeader, SIPURI, 
    Registration, Invitation, Request
)
from sipsimple.account import Account
from sipsimple.application import SIPApplication
from sipsimple.storage import MemoryStorage
from sipsimple.session import Session
from sipsimple.streams import AudioStream
from sipsimple.threading.green import run_in_green_thread

from ..utils.logger import DAHDILogger, log_function_call
from ..utils.config import Config
from ..events.dispatcher import EventDispatcher
from ..events.types import PhoneEvent, CallState, DTMFEvent

# Get structured logger
logger = DAHDILogger().get_logger(__name__)

@dataclass
class AudioConfig:
    """Audio configuration parameters"""
    sample_rate: int = 8000
    channels: int = 1
    bit_depth: int = 16
    ptime: int = 20  # Packet time in ms
    codec: str = 'PCMU'  # Default to G.711 μ-law

@dataclass
class CallSession:
    """Tracks state and metadata for an active call session"""
    session_id: str
    sip_session: Session
    start_time: datetime
    remote_uri: str
    state: CallState
    audio_stream: Optional[AudioStream] = None
    last_activity: Optional[datetime] = None
    dtmf_buffer: str = ''

class SIPServer(SIPApplication):
    """
    Core SIP server implementation using python-sipsimple.
    Handles SIP signaling, audio streaming, and phone state management.
    """
    def __init__(self, event_dispatcher: EventDispatcher):
        self.config = Config()
        self._setup_logging()
        
        # Initialize SIP engine
        SIPApplication.__init__(self)
        self.engine = Engine()
        self.storage = MemoryStorage()
        
        # Event handling
        self.event_dispatcher = event_dispatcher
        
        # Audio configuration
        self.audio_config = AudioConfig(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
            bit_depth=self.config.audio.bit_depth,
            ptime=self.config.audio.ptime,
            codec=self.config.audio.codec
        )
        
        # State tracking
        self.phone_state = CallState.ON_HOOK
        self.registered_devices: Dict[str, Registration] = {}
        self.active_sessions: Dict[str, CallSession] = {}
        self.event_subscribers: Set[Callable] = set()
        
        # Debug tracking
        self.call_history: List[Dict[str, Any]] = []
        
        logger.info("SIP server initialized", 
                   audio_config=self.audio_config.__dict__,
                   debug_enabled=logger.isEnabledFor(logging.DEBUG))

    def _setup_logging(self) -> None:
        """Configure server-specific logging with detailed debug stats"""
        self.debug_stats = {
            'total_calls': 0,
            'active_calls': 0,
            'failed_calls': 0,
            'dtmf_events': 0,
            'audio_streams': 0,
            'registration_attempts': 0,
            'audio_errors': 0,
            'last_error': None
        }
        
        # Set up debug logging handlers
        if logger.isEnabledFor(logging.DEBUG):
            logger.debug("Detailed SIP debugging enabled")
            self.engine.trace_sip = True  # Enable SIP message tracing
            self.engine.log_level = logging.DEBUG

    @log_function_call(level="DEBUG")
    async def start(self) -> None:
        """Start SIP server and initialize resources"""
        try:
            # Start SIP engine with configuration
            self.engine.start(
                auto_sound=False,  # We'll handle audio manually
                udp_port=self.config.server.sip_port,
                tcp_port=self.config.server.sip_port,
                user_agent=f'SIP Phone API {self.config.version}'
            )
            
            # Configure account for HT802 registration
            self.account = Account(self.storage)
            self.account.id = self.config.ht802.username
            self.account.auth.password = self.config.ht802.password
            self.account.sip.outbound_proxy = self.config.ht802.host
            self.account.sip.register = True  # Accept registrations
            self.account.save()
            
            # Start processing
            self.start(storage=self.storage)
            
            logger.info("SIP server started successfully",
                       host=self.config.server.host,
                       port=self.config.server.sip_port,
                       registration_enabled=self.account.sip.register)
            
        except Exception as e:
            logger.error("Failed to start SIP server", 
                        error=str(e),
                        exc_info=True)
            self.debug_stats['last_error'] = str(e)
            raise

    async def stop(self) -> None:
        """Stop server and cleanup resources"""
        try:
            logger.info("Stopping SIP server...")
            
            # End all active calls
            for session in self.active_sessions.values():
                try:
                    await self._end_call(session.session_id)
                except Exception as e:
                    logger.error(f"Error ending call {session.session_id}", exc_info=True)
            
            # Unregister devices
            for reg in self.registered_devices.values():
                try:
                    reg.end()
                except Exception as e:
                    logger.error(f"Error unregistering device", exc_info=True)
            
            # Stop SIP application
            self.stop()
            
            # Stop engine
            self.engine.stop()
            
            logger.info("SIP server stopped successfully",
                       total_calls=self.debug_stats['total_calls'],
                       failed_calls=self.debug_stats['failed_calls'])
            
        except Exception as e:
            logger.error("Error stopping SIP server", exc_info=True)
            self.debug_stats['last_error'] = str(e)
            raise

    @run_in_green_thread
    def _handle_incoming_register(self, request: Request) -> None:
        """Handle incoming REGISTER request"""
        try:
            device_uri = str(request.from_header.uri)
            
            # Validate device
            if device_uri != self.config.ht802.host:
                logger.warning("Rejected registration from unknown device",
                             device=device_uri)
                request.reject(403)  # Forbidden
                return
            
            # Accept registration
            registration = Registration(request)
            self.registered_devices[device_uri] = registration
            
            self.debug_stats['registration_attempts'] += 1
            logger.info("Device registered successfully", 
                       device=device_uri,
                       expires=registration.expires)
            
        except Exception as e:
            logger.error("Error handling REGISTER request", exc_info=True)
            self.debug_stats['last_error'] = str(e)
            request.reject(500)

    @run_in_green_thread
    def _handle_incoming_session(self, session: Session) -> None:
        """Handle incoming SIP session (INVITE)"""
        try:
            remote_uri = str(session.remote_identity.uri)
            
            # Validate source
            if remote_uri not in self.registered_devices:
                logger.warning("Rejected session from unregistered device",
                             source=remote_uri)
                session.reject(403)
                return
            
            # Create session tracking
            session_id = str(uuid.uuid4())
            call_session = CallSession(
                session_id=session_id,
                sip_session=session,
                start_time=datetime.utcnow(),
                remote_uri=remote_uri,
                state=CallState.CONNECTING
            )
            
            # Accept audio stream
            audio_stream = session.proposed_streams[0]
            session.accept([audio_stream])
            
            # Update tracking
            call_session.audio_stream = audio_stream
            call_session.state = CallState.ACTIVE
            self.active_sessions[session_id] = call_session
            
            # Update stats
            self.debug_stats['total_calls'] += 1
            self.debug_stats['active_calls'] += 1
            self.debug_stats['audio_streams'] += 1
            
            # Dispatch event
            self.event_dispatcher.dispatch(PhoneEvent(
                type="call_started",
                call_id=session_id,
                remote_uri=remote_uri,
                timestamp=datetime.utcnow().isoformat()
            ))
            
            logger.info("Call established successfully", 
                       session_id=session_id,
                       remote_uri=remote_uri)
            
        except Exception as e:
            logger.error("Error handling incoming session", exc_info=True)
            self.debug_stats['failed_calls'] += 1
            self.debug_stats['last_error'] = str(e)
            session.reject(500)

    async def _end_call(self, session_id: str) -> None:
        """End an active call session"""
        try:
            if session_id not in self.active_sessions:
                logger.warning("Attempted to end nonexistent call",
                             session_id=session_id)
                return
            
            call_session = self.active_sessions[session_id]
            
            # End SIP session
            call_session.sip_session.end()
            
            # Update state
            call_session.state = CallState.ENDED
            self.debug_stats['active_calls'] -= 1
            
            # Record in history
            self.call_history.append({
                'session_id': session_id,
                'remote_uri': call_session.remote_uri,
                'start_time': call_session.start_time,
                'end_time': datetime.utcnow(),
                'dtmf_count': len(call_session.dtmf_buffer)
            })
            
            # Remove from active sessions
            del self.active_sessions[session_id]
            
            # Dispatch event
            self.event_dispatcher.dispatch(PhoneEvent(
                type="call_ended",
                call_id=session_id,
                timestamp=datetime.utcnow().isoformat()
            ))
            
            logger.info("Call ended successfully",
                       session_id=session_id,
                       duration=(datetime.utcnow() - call_session.start_time).seconds)
            
        except Exception as e:
            logger.error(f"Error ending call {session_id}", exc_info=True)
            self.debug_stats['last_error'] = str(e)

    def _handle_dtmf(self, session: Session, digit: str, duration: int) -> None:
        """Handle DTMF digit from active call"""
        try:
            # Find associated call session
            session_id = None
            for sid, call in self.active_sessions.items():
                if call.sip_session == session:
                    session_id = sid
                    break
            
            if not session_id:
                logger.error("Received DTMF for unknown session")
                return
            
            # Update state
            call_session = self.active_sessions[session_id]
            call_session.dtmf_buffer += digit
            call_session.last_activity = datetime.utcnow()
            
            self.debug_stats['dtmf_events'] += 1
            
            # Dispatch event
            self.event_dispatcher.dispatch(DTMFEvent(
                digit=digit,
                duration=duration,
                call_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                sequence=len(call_session.dtmf_buffer)
            ))
            
            logger.info("DTMF processed",
                       digit=digit,
                       session_id=session_id,
                       buffer=call_session.dtmf_buffer)
            
        except Exception as e:
            logger.error("Error handling DTMF", exc_info=True)
            self.debug_stats['last_error'] = str(e)

    def _handle_audio(self, session: Session, audio_data: bytes) -> None:
        """Handle RTP audio data from active call"""
        try:
            # Find associated call session
            session_id = None
            for sid, call in self.active_sessions.items():
                if call.sip_session == session:
                    session_id = sid
                    break
            
            if not session_id:
                logger.error("Received audio for unknown session")
                return
            
            call_session = self.active_sessions[session_id]
            
            # Process audio based on codec
            if self.audio_config.codec == 'PCMU':
                # Convert μ-law to PCM if needed
                audio_data = audioop.ulaw2lin(audio_data, 2)
            elif self.audio_config.codec == 'PCMA':
                # Convert A-law to PCM if needed
                audio_data = audioop.alaw2lin(audio_data, 2)
            
            # Basic audio level detection for logging
            max_sample = max(array.array('h', audio_data))
            if max_sample > 8000:  # Voice activity threshold
                logger.debug("Voice activity detected",
                           level=max_sample,
                           session_id=session_id)
            
            # Forward audio through event system
            self.event_dispatcher.dispatch(PhoneEvent(
                type="audio_data",
                call_id=session_id,
                timestamp=datetime.utcnow().isoformat(),
                data=audio_data
            ))
            
        except Exception as e:
            logger.error("Error processing audio", exc_info=True)
            self.debug_stats['audio_errors'] += 1
            self.debug_stats['last_error'] = str(e)

    @run_in_green_thread
    def ring(self, duration: int = 2000) -> None:
        """Trigger phone to ring"""
        try:
            # Create INVITE for ring
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
            
            logger.info("Ring completed successfully", 
                       duration=duration)
            
        except Exception as e:
            logger.error("Error triggering ring", exc_info=True)
            self.debug_stats['last_error'] = str(e)
            raise

    async def get_state(self) -> dict:
        """Get comprehensive server state"""
        active_calls = [{
            'session_id': sid,
            'remote_uri': session.remote_uri,
            'state': session.state.value,
            'duration': (datetime.utcnow() - session.start_time).seconds,
            'dtmf_buffer': session.dtmf_buffer
        } for sid, session in self.active_sessions.items()]
        
        return {
            "registered_devices": list(self.registered_devices.keys()),
            "active_calls": active_calls,
            "call_history": self.call_history[-10:],  # Last 10 calls
            "debug_stats": self.debug_stats
        }

# Example usage:
"""
from events.dispatcher import EventDispatcher

dispatcher = EventDispatcher()
server = SIPServer(dispatcher)

# Start server
await server.start()

# Subscribe to events
async def handle_event(event):
    print(f"Event received: {event}")
dispatcher.subscribe(handle_event)

# Ring the phone
await server.ring(2000)

# Get current state
state = await server.get_state()
print(f"Server state: {state}")

# Cleanup
await server.stop()
"""
