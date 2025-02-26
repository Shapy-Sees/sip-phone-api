# src/sip_phone/core/pjsip_server.py
"""
Core SIP server implementation for Smart Home Phone Integration using PJSIP/PJSUA2.
Replaces the original SIPSimple implementation with PJSIP for better compatibility and reliability.

This server handles:
- SIP signaling (REGISTER, INVITE, BYE)
- RTP audio stream management
- Call state tracking
- Event dispatching
- DTMF detection
- Comprehensive logging for debugging
"""

import asyncio
import logging
import os
import time
import uuid
import threading
import wave
import audioop
import array
from typing import Dict, Optional, Set, Callable, Any, List
from datetime import datetime
from dataclasses import dataclass
import pjsua2 as pj

from ..utils.logger import SIPLogger, log_function_call
from ..utils.config import Config
from ..events.dispatcher import EventDispatcher
from ..events.types import PhoneEvent, CallState, DTMFEvent

# Get structured logger
logger = SIPLogger().get_logger(__name__)

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
    call: Any  # pj.Call object
    start_time: datetime
    remote_uri: str
    state: CallState
    audio_media: Optional[Any] = None  # pj.AudioMedia
    last_activity: Optional[datetime] = None
    dtmf_buffer: str = ''

# Custom PJSUA2 callback classes
class MyAccountCallback(pj.AccountCallback):
    """Callback for SIP account events"""
    
    def __init__(self, account, server):
        pj.AccountCallback.__init__(self, account)
        self.server = server
        self.logger = SIPLogger().get_logger(__name__ + ".AccountCallback")

    def onRegState(self, info):
        """Called when registration state changes"""
        if info.regIsActive:
            self.logger.info(f"Registration active, expires in {info.regExpiresSec} seconds")
        else:
            self.logger.warning(f"Registration inactive: {info.regStatusText}")

    def onIncomingCall(self, call):
        """Called when there's an incoming call"""
        self.logger.info("Incoming call received")
        self.server._handle_incoming_call(call)

class MyCallCallback(pj.CallCallback):
    """Callback for SIP call events"""
    
    def __init__(self, call, server, session_id):
        pj.CallCallback.__init__(self, call)
        self.server = server
        self.session_id = session_id
        self.logger = SIPLogger().get_logger(__name__ + ".CallCallback")
        self.call_connected = False

    def onCallState(self, call):
        """Called when call state changes"""
        ci = call.getInfo()
        state_str = {
            pj.PJSIP_INV_STATE_NULL: "NULL",
            pj.PJSIP_INV_STATE_CALLING: "CALLING",
            pj.PJSIP_INV_STATE_INCOMING: "INCOMING",
            pj.PJSIP_INV_STATE_EARLY: "EARLY",
            pj.PJSIP_INV_STATE_CONNECTING: "CONNECTING",
            pj.PJSIP_INV_STATE_CONFIRMED: "CONFIRMED",
            pj.PJSIP_INV_STATE_DISCONNECTED: "DISCONNECTED"
        }.get(ci.state, "UNKNOWN")
        
        self.logger.info(f"Call state changed to {state_str}")
        
        if ci.state == pj.PJSIP_INV_STATE_CONFIRMED:
            self.call_connected = True
            asyncio.create_task(self.server._call_connected(self.session_id))
        elif ci.state == pj.PJSIP_INV_STATE_DISCONNECTED:
            if self.call_connected:
                asyncio.create_task(self.server._call_disconnected(self.session_id))
            else:
                asyncio.create_task(self.server._call_failed(self.session_id))

    def onCallMediaState(self, call):
        """Called when media state changes"""
        ci = call.getInfo()
        self.logger.info(f"Call media state changed: {ci.mediaStatus}")
        
        if ci.mediaStatus == pj.PJSUA_CALL_MEDIA_ACTIVE:
            # Connect audio media
            call_media = call.getMedia(0)
            if call_media:
                audio_media = call_media.getAudioMedia()
                if audio_media:
                    self.server._handle_audio_media(self.session_id, audio_media)

    def onDtmfDigit(self, call, digit):
        """Called when DTMF digit is received"""
        self.logger.info(f"DTMF digit received: {digit}")
        self.server._handle_dtmf(self.session_id, digit, 200)  # Assume 200ms duration

    def onCallTransferStatus(self, call, status_code, status_text, final, cont):
        """Called when call transfer status changes"""
        self.logger.info(f"Call transfer status: {status_code} {status_text}")
        return cont

class AudioCaptureCallback(pj.AudioMediaCallback):
    """Callback for audio capture"""
    
    def __init__(self, server, session_id):
        pj.AudioMediaCallback.__init__(self)
        self.server = server
        self.session_id = session_id
        self.logger = SIPLogger().get_logger(__name__ + ".AudioCapture")

    def onFrameRequested(self, frame):
        """Called when audio frame is requested"""
        # This would be used for sending audio to the call
        pass

class AudioPlaybackCallback(pj.AudioMediaCallback):
    """Callback for audio playback"""
    
    def __init__(self, server, session_id):
        pj.AudioMediaCallback.__init__(self)
        self.server = server
        self.session_id = session_id
        self.logger = SIPLogger().get_logger(__name__ + ".AudioPlayback")

    def onFrameReceived(self, frame):
        """Called when audio frame is received"""
        # Process received audio
        self.server._handle_audio_frame(self.session_id, frame)

class SIPServer:
    """
    Core SIP server implementation using PJSIP/PJSUA2.
    Handles SIP signaling, audio streaming, and phone state management.
    """
    def __init__(self, event_dispatcher: EventDispatcher, state_manager=None):
        self.config = Config()
        self._setup_logging()
        
        # Event handling
        self.event_dispatcher = event_dispatcher
        
        # State management
        from .state_manager import StateManager
        self.state_manager = state_manager or StateManager(self.config)
        
        # Audio configuration
        self.audio_config = AudioConfig(
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
            bit_depth=16,  # Fixed value since not in config
            ptime=20,  # Fixed value since not in config
            codec=self.config.audio.codec
        )
        
        # PJSIP objects
        self.ep = None  # Endpoint
        self.transport = None  # Transport
        self.account = None  # Account
        self.account_cb = None  # Account callback
        
        # Call tracking
        self.active_sessions: Dict[str, CallSession] = {}
        self.call_callbacks: Dict[str, MyCallCallback] = {}
        self.audio_callbacks: Dict[str, Dict[str, Any]] = {}
        
        # Debug tracking
        self.call_history: List[Dict[str, Any]] = []
        
        # Thread management
        self.pjsip_thread = None
        self.running = False
        
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

    def _pjsip_log_cb(self, level, msg, length):
        """Callback for PJSIP logging"""
        if level == 1:  # Error
            logger.error(f"PJSIP: {msg}")
        elif level == 2:  # Warning
            logger.warning(f"PJSIP: {msg}")
        elif level == 3:  # Info
            logger.info(f"PJSIP: {msg}")
        elif level == 4:  # Debug
            logger.debug(f"PJSIP: {msg}")
        elif level >= 5:  # Trace
            logger.debug(f"PJSIP TRACE: {msg}")

    def _pjsip_thread_func(self):
        """Thread function for PJSIP event handling"""
        while self.running:
            self.ep.libHandleEvents(100)  # 100ms timeout

    @log_function_call(level="DEBUG")
    async def start(self) -> None:
        """Start SIP server and initialize resources"""
        try:
            # Create endpoint
            self.ep = pj.Endpoint()
            
            # Create endpoint configuration
            ep_cfg = pj.EpConfig()
            
            # Configure logging
            log_level = int(os.environ.get('PJSIP_LOG_LEVEL', '3'))  # Default to INFO
            ep_cfg.logConfig.level = log_level
            ep_cfg.logConfig.consoleLevel = log_level
            
            # Initialize endpoint
            self.ep.libCreate()
            self.ep.libInit(ep_cfg)
            
            # Create SIP transport
            transport_cfg = pj.TransportConfig()
            sip_port = int(self.config.sip.server.split(':')[-1])
            transport_cfg.port = sip_port
            self.transport = self.ep.transportCreate(pj.PJSIP_TRANSPORT_UDP, transport_cfg)
            
            # Start endpoint
            self.ep.libStart()
            
            # Create account configuration
            acc_cfg = pj.AccountConfig()
            acc_cfg.idUri = f"sip:{self.config.hardware.ht802['username']}@{self.config.hardware.ht802['host']}"
            acc_cfg.regConfig.registrarUri = f"sip:{self.config.hardware.ht802['host']}"
            
            # Set credentials if needed
            if self.config.hardware.ht802.get('auth_enabled', False):
                cred = pj.AuthCredInfo(
                    "digest",
                    "*",
                    self.config.hardware.ht802['username'],
                    0,  # Data type (0 for plaintext)
                    self.config.hardware.ht802['password']
                )
                acc_cfg.sipConfig.authCreds.append(cred)
            
            # Create account
            self.account = pj.Account()
            self.account_cb = MyAccountCallback(self.account, self)
            self.account.create(acc_cfg, True, self.account_cb)
            
            # Start PJSIP thread
            self.running = True
            self.pjsip_thread = threading.Thread(target=self._pjsip_thread_func)
            self.pjsip_thread.daemon = True
            self.pjsip_thread.start()
            
            logger.info("SIP server started successfully",
                       host=self.config.hardware.ht802['host'],
                       port=sip_port)
            
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
            for session in list(self.active_sessions.keys()):
                try:
                    await self._end_call(session)
                except Exception as e:
                    logger.error(f"Error ending call {session}", exc_info=True)
            
            # Stop PJSIP thread
            self.running = False
            if self.pjsip_thread:
                self.pjsip_thread.join(2.0)  # Wait up to 2 seconds
            
            # Clean up PJSIP resources
            if self.account:
                self.account.shutdown()
            
            if self.ep:
                self.ep.libDestroy()
            
            logger.info("SIP server stopped successfully",
                       total_calls=self.debug_stats['total_calls'],
                       failed_calls=self.debug_stats['failed_calls'])
            
        except Exception as e:
            logger.error("Error stopping SIP server", exc_info=True)
            self.debug_stats['last_error'] = str(e)
            raise

    def _handle_incoming_call(self, call) -> None:
        """Handle incoming SIP call"""
        try:
            # Create session ID
            session_id = str(uuid.uuid4())
            
            # Create call callback
            call_cb = MyCallCallback(call, self, session_id)
            call.setCallback(call_cb)
            
            # Get call info
            ci = call.getInfo()
            remote_uri = ci.remoteUri
            
            # Create call session
            call_session = CallSession(
                session_id=session_id,
                call=call,
                start_time=datetime.utcnow(),
                remote_uri=remote_uri,
                state=CallState.CONNECTING
            )
            
            # Store session and callback
            self.active_sessions[session_id] = call_session
            self.call_callbacks[session_id] = call_cb
            
            # Update stats
            self.debug_stats['total_calls'] += 1
            self.debug_stats['active_calls'] += 1
            
            # Auto-answer the call
            call_prm = pj.CallOpParam(True)
            call.answer(200, call_prm)  # 200 OK
            
            logger.info("Incoming call auto-answered", 
                       session_id=session_id,
                       remote_uri=remote_uri)
            
        except Exception as e:
            logger.error("Error handling incoming call", exc_info=True)
            self.debug_stats['failed_calls'] += 1
            self.debug_stats['last_error'] = str(e)
            try:
                call_prm = pj.CallOpParam(True)
                call_prm.statusCode = 500  # Internal Server Error
                call.hangup(call_prm)
            except:
                pass

    async def _call_connected(self, session_id: str) -> None:
        """Handle call connected event"""
        try:
            if session_id not in self.active_sessions:
                logger.warning("Call connected for unknown session", session_id=session_id)
                return
            
            call_session = self.active_sessions[session_id]
            call_session.state = CallState.ACTIVE
            
            # Update state manager
            await self.state_manager.transition_to(
                CallState.OFF_HOOK,
                metadata={
                    'call_id': session_id,
                    'remote_uri': call_session.remote_uri,
                    'reason': 'incoming_call'
                }
            )
            
            # Start call in state manager
            await self.state_manager.start_call(
                call_id=session_id,
                remote_uri=call_session.remote_uri
            )
            
            # Dispatch event
            self.event_dispatcher.dispatch(PhoneEvent(
                type="call_started",
                call_id=session_id,
                remote_uri=call_session.remote_uri,
                timestamp=datetime.utcnow().isoformat()
            ))
            
            logger.info("Call established successfully", 
                       session_id=session_id,
                       remote_uri=call_session.remote_uri)
            
        except Exception as e:
            logger.error("Error handling call connected", exc_info=True)
            self.debug_stats['last_error'] = str(e)

    async def _call_disconnected(self, session_id: str) -> None:
        """Handle call disconnected event"""
        try:
            await self._end_call(session_id)
        except Exception as e:
            logger.error("Error handling call disconnected", exc_info=True)
            self.debug_stats['last_error'] = str(e)

    async def _call_failed(self, session_id: str) -> None:
        """Handle call failed event"""
        try:
            if session_id not in self.active_sessions:
                logger.warning("Call failed for unknown session", session_id=session_id)
                return
            
            call_session = self.active_sessions[session_id]
            call_session.state = CallState.ERROR
            
            # Update stats
            self.debug_stats['failed_calls'] += 1
            
            # Clean up resources
            await self._end_call(session_id)
            
            logger.warning("Call failed", 
                         session_id=session_id,
                         remote_uri=call_session.remote_uri)
            
        except Exception as e:
            logger.error("Error handling call failure", exc_info=True)
            self.debug_stats['last_error'] = str(e)

    def _handle_audio_media(self, session_id: str, audio_media) -> None:
        """Handle audio media for a call"""
        try:
            if session_id not in self.active_sessions:
                logger.warning("Audio media for unknown session", session_id=session_id)
                return
            
            call_session = self.active_sessions[session_id]
            call_session.audio_media = audio_media
            
            # Create audio callbacks
            capture_cb = AudioCaptureCallback(self, session_id)
            playback_cb = AudioPlaybackCallback(self, session_id)
            
            # Store callbacks
            self.audio_callbacks[session_id] = {
                'capture': capture_cb,
                'playback': playback_cb
            }
            
            # Register callbacks
            audio_media.startTransmit(self.ep.audDevManager().getPlaybackDevMedia())
            self.ep.audDevManager().getCaptureDevMedia().startTransmit(audio_media)
            
            # Update stats
            self.debug_stats['audio_streams'] += 1
            
            logger.info("Audio media established", 
                       session_id=session_id)
            
        except Exception as e:
            logger.error("Error handling audio media", exc_info=True)
            self.debug_stats['audio_errors'] += 1
            self.debug_stats['last_error'] = str(e)

    def _handle_audio_frame(self, session_id: str, frame) -> None:
        """Handle audio frame from a call"""
        try:
            if session_id not in self.active_sessions:
                return
            
            # Extract audio data from frame
            audio_data = bytes(frame.buf)
            
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
            logger.error("Error processing audio frame", exc_info=True)
            self.debug_stats['audio_errors'] += 1
            self.debug_stats['last_error'] = str(e)

    def _handle_dtmf(self, session_id: str, digit: str, duration: int) -> None:
        """Handle DTMF digit from active call"""
        try:
            if session_id not in self.active_sessions:
                logger.error("Received DTMF for unknown session")
                return
            
            # Update state
            call_session = self.active_sessions[session_id]
            call_session.dtmf_buffer += digit
            call_session.last_activity = datetime.utcnow()
            
            self.debug_stats['dtmf_events'] += 1
            
            # Update state manager
            asyncio.create_task(self.state_manager.update_call_metadata(
                call_id=session_id,
                dtmf=digit,
                custom_data={'duration': duration}
            ))
            
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

    async def _end_call(self, session_id: str) -> None:
        """End an active call session"""
        try:
            if session_id not in self.active_sessions:
                logger.warning("Attempted to end nonexistent call",
                             session_id=session_id)
                return
            
            call_session = self.active_sessions[session_id]
            
            # End call
            try:
                call_prm = pj.CallOpParam(True)
                call_session.call.hangup(call_prm)
            except Exception as e:
                logger.warning(f"Error hanging up call: {e}")
            
            # Clean up audio callbacks
            if session_id in self.audio_callbacks:
                del self.audio_callbacks[session_id]
            
            # Clean up call callback
            if session_id in self.call_callbacks:
                del self.call_callbacks[session_id]
            
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
            
            # Update state manager
            await self.state_manager.end_call(session_id)
            
            # Transition to on-hook if no active calls
            if not self.active_sessions:
                await self.state_manager.transition_to(
                    CallState.ON_HOOK,
                    metadata={
                        'call_id': session_id,
                        'reason': 'call_ended'
                    }
                )
            
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

    async def ring(self, duration: int = 2000) -> None:
        """Trigger phone to ring"""
        try:
            # Update state manager
            await self.state_manager.transition_to(
                CallState.RINGING,
                metadata={
                    'duration': duration,
                    'reason': 'ring_request'
                }
            )
            
            # Create call
            call = pj.Call(self.account)
            
            # Create session ID
            session_id = str(uuid.uuid4())
            
            # Create call callback
            call_cb = MyCallCallback(call, self, session_id)
            call.setCallback(call_cb)
            
            # Make call to HT802
            call_prm = pj.CallOpParam(True)
            call_prm.opt.audioCount = 1
            call_prm.opt.videoCount = 0
            
            # Set destination URI
            uri = f"sip:{self.config.hardware.ht802['host']}"
            call.makeCall(uri, call_prm)
            
            # Wait for duration
            await asyncio.sleep(duration / 1000)
            
            # End call
            try:
                call_prm = pj.CallOpParam(True)
                call.hangup(call_prm)
            except Exception as e:
                logger.warning(f"Error hanging up ring call: {e}")
            
            # Return to on-hook state
            await self.state_manager.transition_to(
                CallState.ON_HOOK,
                metadata={
                    'reason': 'ring_completed'
                }
            )
            
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
            "registered_devices": [self.config.hardware.ht802['host']] if self.account and self.account.isValid() else [],
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

# Ring the phone
await server.ring(2000)

# Get current state
state = await server.get_state()
print(f"Server state: {state}")

# Cleanup
await server.stop()
"""
