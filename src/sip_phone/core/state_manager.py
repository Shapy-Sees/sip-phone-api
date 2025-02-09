# src/sip_phone/core/state_manager.py
"""
State management system for the SIP Phone API.
Handles phone state tracking, transitions, persistence, and event notifications.

This module is responsible for:
- Tracking phone state (on-hook, off-hook, ringing, in-call)
- Managing state transitions
- Providing state change notifications through the event system
- Handling call metadata
- State persistence
- Comprehensive logging
"""

import json
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, Set, Any, List
from dataclasses import dataclass, asdict
from pathlib import Path

from ..events.dispatcher import event_dispatcher
from ..events.types import (
    CallState,
    EventType,
    BaseEvent,
    PhoneEvent,
    SystemEvent
)
from ..utils.logger import SIPLogger, log_function_call
from ..utils.config import Config

# Get logger instance
logger = SIPLogger().get_logger(__name__)

@dataclass
class CallMetadata:
    """Metadata for active calls"""
    call_id: str
    remote_uri: str
    start_time: datetime
    dtmf_sequence: str = ""
    duration: Optional[int] = None
    last_activity: Optional[datetime] = None
    custom_data: Dict[str, Any] = None

class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted"""
    pass

class StateManager:
    """
    Manages phone state, transitions, and persistence.
    Integrates with event system for notifications.
    """
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        CallState.ON_HOOK: {CallState.RINGING, CallState.OFF_HOOK},
        CallState.OFF_HOOK: {CallState.ON_HOOK, CallState.CONNECTING},
        CallState.RINGING: {CallState.ON_HOOK, CallState.ACTIVE},
        CallState.CONNECTING: {CallState.ACTIVE, CallState.ERROR, CallState.ON_HOOK},
        CallState.ACTIVE: {CallState.ON_HOOK, CallState.ERROR},
        CallState.ERROR: {CallState.ON_HOOK},
        CallState.ENDED: {CallState.ON_HOOK}
    }

    def __init__(self, config: Config):
        """Initialize the state manager"""
        self.config = config
        
        # Current state
        self._current_state = CallState.ON_HOOK
        
        # Active call tracking
        self._active_calls: Dict[str, CallMetadata] = {}
        
        # State persistence
        self._state_file = Path(self.config.paths.data_dir) / "state.json"
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Restore state if available
        self._restore_state()
        
        # Debug tracking
        self._transition_history: List[Dict[str, Any]] = []
        self._error_count = 0
        
        logger.info("State manager initialized",
                   initial_state=self._current_state,
                   persistence_path=str(self._state_file))

    @property
    def current_state(self) -> CallState:
        """Get current phone state"""
        return self._current_state

    @property
    def active_calls(self) -> Dict[str, CallMetadata]:
        """Get active call metadata"""
        return self._active_calls.copy()

    @log_function_call(level="DEBUG")
    async def transition_to(self, new_state: CallState, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Transition to a new state if valid.
        
        Args:
            new_state: Target state to transition to
            metadata: Optional metadata about the transition
        
        Raises:
            StateTransitionError: If transition is invalid
        """
        try:
            # Validate transition
            if new_state not in self.VALID_TRANSITIONS[self._current_state]:
                raise StateTransitionError(
                    f"Invalid transition: {self._current_state} -> {new_state}"
                )
            
            old_state = self._current_state
            self._current_state = new_state
            
            # Update transition history
            self._transition_history.append({
                'timestamp': datetime.utcnow().isoformat(),
                'from_state': old_state,
                'to_state': new_state,
                'metadata': metadata or {}
            })
            
            # Persist state change
            await self._persist_state()
            
            # Dispatch state change event
            await event_dispatcher.dispatch(StateEvent(
                event_id=f"state_{datetime.utcnow().timestamp()}",
                previous_state=old_state,
                new_state=new_state,
                call_id=metadata.get('call_id') if metadata else None,
                reason=metadata.get('reason') if metadata else None,
                metadata=metadata or {}
            ))
            
            logger.info("State transition successful",
                       old_state=old_state,
                       new_state=new_state,
                       metadata=metadata)
            
        except Exception as e:
            self._error_count += 1
            logger.error("State transition failed",
                        error=str(e),
                        old_state=self._current_state,
                        attempted_state=new_state,
                        exc_info=True)
            
            # Dispatch error event
            await event_dispatcher.dispatch(SystemEvent(
                level="error",
                component="state_manager",
                message=f"State transition failed: {str(e)}",
                error=str(e)
            ))
            raise

    @log_function_call(level="DEBUG")
    async def start_call(self, call_id: str, remote_uri: str) -> None:
        """
        Start tracking a new call.
        
        Args:
            call_id: Unique identifier for the call
            remote_uri: Remote SIP URI for the call
        """
        try:
            # Create call metadata
            call_meta = CallMetadata(
                call_id=call_id,
                remote_uri=remote_uri,
                start_time=datetime.utcnow()
            )
            
            # Track call
            self._active_calls[call_id] = call_meta
            
            # Transition state
            await self.transition_to(
                CallState.ACTIVE,
                metadata={
                    'call_id': call_id,
                    'remote_uri': remote_uri
                }
            )
            
            logger.info("Call started",
                       call_id=call_id,
                       remote_uri=remote_uri)
            
        except Exception as e:
            logger.error("Failed to start call",
                        call_id=call_id,
                        error=str(e),
                        exc_info=True)
            raise

    @log_function_call(level="DEBUG")
    async def end_call(self, call_id: str) -> None:
        """
        End tracking for a call.
        
        Args:
            call_id: ID of call to end
        """
        try:
            if call_id not in self._active_calls:
                logger.warning("Attempted to end nonexistent call",
                             call_id=call_id)
                return
            
            # Get call metadata
            call_meta = self._active_calls[call_id]
            
            # Calculate duration
            end_time = datetime.utcnow()
            duration = int((end_time - call_meta.start_time).total_seconds())
            call_meta.duration = duration
            
            # Remove from active calls
            del self._active_calls[call_id]
            
            # Transition state if no other active calls
            if not self._active_calls:
                await self.transition_to(
                    CallState.ON_HOOK,
                    metadata={
                        'call_id': call_id,
                        'duration': duration
                    }
                )
            
            logger.info("Call ended",
                       call_id=call_id,
                       duration=duration,
                       dtmf_count=len(call_meta.dtmf_sequence))
            
        except Exception as e:
            logger.error("Failed to end call",
                        call_id=call_id,
                        error=str(e),
                        exc_info=True)
            raise

    @log_function_call(level="DEBUG")
    async def update_call_metadata(
        self,
        call_id: str,
        dtmf: Optional[str] = None,
        custom_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Update metadata for an active call.
        
        Args:
            call_id: ID of call to update
            dtmf: DTMF digit to append to sequence
            custom_data: Custom metadata to update/add
        """
        try:
            if call_id not in self._active_calls:
                logger.warning("Attempted to update nonexistent call",
                             call_id=call_id)
                return
            
            call_meta = self._active_calls[call_id]
            
            # Update DTMF sequence
            if dtmf:
                call_meta.dtmf_sequence += dtmf
            
            # Update custom data
            if custom_data:
                if call_meta.custom_data is None:
                    call_meta.custom_data = {}
                call_meta.custom_data.update(custom_data)
            
            # Update last activity
            call_meta.last_activity = datetime.utcnow()
            
            logger.debug("Call metadata updated",
                        call_id=call_id,
                        dtmf_sequence=call_meta.dtmf_sequence,
                        custom_data=call_meta.custom_data)
            
        except Exception as e:
            logger.error("Failed to update call metadata",
                        call_id=call_id,
                        error=str(e),
                        exc_info=True)
            raise

    async def _persist_state(self) -> None:
        """Persist current state and metadata to disk"""
        try:
            state_data = {
                'current_state': self._current_state,
                'timestamp': datetime.utcnow().isoformat(),
                'active_calls': {
                    call_id: asdict(meta)
                    for call_id, meta in self._active_calls.items()
                },
                'transition_history': self._transition_history[-10:],  # Keep last 10
                'error_count': self._error_count
            }
            
            # Write atomically using temporary file
            temp_file = self._state_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state_data, f, indent=2)
            temp_file.replace(self._state_file)
            
            logger.debug("State persisted successfully",
                        path=str(self._state_file))
            
        except Exception as e:
            logger.error("Failed to persist state",
                        error=str(e),
                        exc_info=True)
            
            # Dispatch error event
            await event_dispatcher.dispatch(SystemEvent(
                level="error",
                component="state_manager",
                message=f"Failed to persist state: {str(e)}",
                error=str(e)
            ))

    def _restore_state(self) -> None:
        """Restore state from disk if available"""
        try:
            if not self._state_file.exists():
                logger.info("No persistent state found")
                return
            
            with open(self._state_file) as f:
                state_data = json.load(f)
            
            # Restore basic state
            self._current_state = CallState(state_data['current_state'])
            self._error_count = state_data.get('error_count', 0)
            self._transition_history = state_data.get('transition_history', [])
            
            # Restore call metadata
            for call_id, meta in state_data.get('active_calls', {}).items():
                self._active_calls[call_id] = CallMetadata(**meta)
            
            logger.info("State restored successfully",
                       current_state=self._current_state,
                       active_calls=len(self._active_calls))
            
        except Exception as e:
            logger.error("Failed to restore state",
                        error=str(e),
                        exc_info=True)
            
            # Use default state
            self._current_state = CallState.ON_HOOK
            self._active_calls = {}

    async def get_debug_info(self) -> Dict[str, Any]:
        """Get debug information about state manager"""
        return {
            'current_state': self._current_state,
            'active_calls': len(self._active_calls),
            'transition_history': self._transition_history,
            'error_count': self._error_count,
            'persistence_path': str(self._state_file)
        }

# Example usage:
"""
from utils.config import Config

config = Config()
state_manager = StateManager(config)

# Start a call
await state_manager.start_call(
    call_id="abc123",
    remote_uri="sip:1234@example.com"
)

# Update call metadata
await state_manager.update_call_metadata(
    call_id="abc123",
    dtmf="5",
    custom_data={'caller_name': 'John'}
)

# End call
await state_manager.end_call("abc123")

# Get debug info
debug_info = await state_manager.get_debug_info()
print(f"State manager status: {debug_info}")
"""
