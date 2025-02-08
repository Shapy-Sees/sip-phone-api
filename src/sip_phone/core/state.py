# src/sip_phone/core/state_manager.py
"""
State management system for SIP Phone API.
Provides thread-safe state tracking, state transition management,
and event notifications for phone status changes.
Integrates with logging system for comprehensive state change tracking.
"""

import asyncio
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Set, Callable
import threading

from ..utils.logger import SIPLogger, log_function_call
from ..utils.config import Config

# Get logger instance
logger = SIPLogger().get_logger(__name__)

class PhoneState(Enum):
    """Enumeration of possible phone states"""
    ON_HOOK = "on_hook"
    OFF_HOOK = "off_hook"
    RINGING = "ringing"
    IN_CALL = "in_call"
    ERROR = "error"

@dataclass
class CallInfo:
    """Information about current/last call"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    remote_party: Optional[str] = None
    direction: Optional[str] = None
    call_id: Optional[str] = None

class StateTransitionError(Exception):
    """Exception raised for invalid state transitions"""
    pass

class StateManager:
    """
    Thread-safe state manager for phone system.
    Handles state transitions, event notifications, and state persistence.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance

    def __init__(self):
        with self._lock:
            if not hasattr(self, '_initialized'):
                self._current_state = PhoneState.ON_HOOK
                self._last_dtmf = None
                self._call_info = CallInfo()
                self._subscribers: Set[Callable] = set()
                self._error_condition = None
                self._state_history: list = []
                self._max_history = 100
                self._stats = {
                    'state_changes': 0,
                    'dtmf_events': 0,
                    'errors': 0,
                    'total_calls': 0,
                    'last_state_change': None
                }
                self._initialized = True
                logger.info("State manager initialized",
                          initial_state=self._current_state.value)

    @property
    def current_state(self) -> PhoneState:
        """Get current phone state"""
        with self._lock:
            return self._current_state

    @log_function_call(level="DEBUG")
    async def transition_to(self, new_state: PhoneState, **kwargs) -> None:
        """
        Transition to a new state with validation.
        
        Args:
            new_state: Target phone state
            **kwargs: Additional transition parameters
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        try:
            with self._lock:
                old_state = self._current_state
                
                # Validate transition
                if not self._is_valid_transition(old_state, new_state):
                    raise StateTransitionError(
                        f"Invalid transition from {old_state.value} to {new_state.value}"
                    )
                
                # Update state
                self._current_state = new_state
                self._stats['state_changes'] += 1
                self._stats['last_state_change'] = datetime.utcnow().isoformat()
                
                # Update call info if needed
                if new_state == PhoneState.IN_CALL:
                    self._call_info = CallInfo(
                        start_time=datetime.utcnow(),
                        remote_party=kwargs.get('remote_party'),
                        direction=kwargs.get('direction'),
                        call_id=kwargs.get('call_id')
                    )
                    self._stats['total_calls'] += 1
                elif old_state == PhoneState.IN_CALL:
                    self._call_info.end_time = datetime.utcnow()
                
                # Add to history
                self._add_to_history(old_state, new_state, kwargs)
                
                logger.info("State transition",
                          old_state=old_state.value,
                          new_state=new_state.value,
                          **kwargs)
                
                # Notify subscribers
                await self._notify_subscribers({
                    "type": "state_change",
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "timestamp": datetime.utcnow().isoformat(),
                    **kwargs
                })
                
        except Exception as e:
            logger.error("State transition failed",
                        error=str(e),
                        old_state=old_state.value,
                        new_state=new_state.value,
                        exc_info=True)
            raise

    def _is_valid_transition(self, from_state: PhoneState, to_state: PhoneState) -> bool:
        """
        Validate state transition.
        
        Args:
            from_state: Current state
            to_state: Target state
            
        Returns:
            bool: True if transition is valid
        """
        # Define valid transitions
        valid_transitions = {
            PhoneState.ON_HOOK: {PhoneState.RINGING, PhoneState.OFF_HOOK, PhoneState.ERROR},
            PhoneState.OFF_HOOK: {PhoneState.ON_HOOK, PhoneState.IN_CALL, PhoneState.ERROR},
            PhoneState.RINGING: {PhoneState.ON_HOOK, PhoneState.OFF_HOOK, PhoneState.ERROR},
            PhoneState.IN_CALL: {PhoneState.ON_HOOK, PhoneState.ERROR},
            PhoneState.ERROR: {PhoneState.ON_HOOK}  # Can only recover to on_hook
        }
        
        return to_state in valid_transitions.get(from_state, set())

    def _add_to_history(self, old_state: PhoneState, new_state: PhoneState, details: Dict) -> None:
        """Add state transition to history with rotation"""
        self._state_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "old_state": old_state.value,
            "new_state": new_state.value,
            "details": details
        })
        
        # Rotate history if needed
        if len(self._state_history) > self._max_history:
            self._state_history.pop(0)

    @log_function_call(level="DEBUG")
    async def record_dtmf(self, digit: str) -> None:
        """
        Record DTMF digit and notify subscribers.
        
        Args:
            digit: DTMF digit received
        """
        with self._lock:
            self._last_dtmf = digit
            self._stats['dtmf_events'] += 1
            
            logger.debug("DTMF recorded", digit=digit)
            
            await self._notify_subscribers({
                "type": "dtmf",
                "digit": digit,
                "timestamp": datetime.utcnow().isoformat()
            })

    @log_function_call(level="DEBUG")
    async def set_error(self, error_condition: str) -> None:
        """
        Set error state with condition.
        
        Args:
            error_condition: Description of error
        """
        with self._lock:
            self._error_condition = error_condition
            self._stats['errors'] += 1
            
            logger.error("Error state set", error_condition=error_condition)
            
            await self.transition_to(
                PhoneState.ERROR,
                error_condition=error_condition
            )

    async def subscribe(self, callback: Callable) -> None:
        """
        Subscribe to state change notifications.
        
        Args:
            callback: Async function to call on state changes
        """
        with self._lock:
            self._subscribers.add(callback)
            logger.debug("Subscriber added",
                        total_subscribers=len(self._subscribers))

    async def unsubscribe(self, callback: Callable) -> None:
        """
        Unsubscribe from state change notifications.
        
        Args:
            callback: Previously registered callback
        """
        with self._lock:
            self._subscribers.discard(callback)
            logger.debug("Subscriber removed",
                        total_subscribers=len(self._subscribers))

    async def _notify_subscribers(self, event: Dict) -> None:
        """
        Notify all subscribers of an event.
        
        Args:
            event: Event data to send to subscribers
        """
        for callback in self._subscribers:
            try:
                await callback(event)
            except Exception as e:
                logger.error("Subscriber notification failed",
                           error=str(e),
                           exc_info=True)

    @log_function_call(level="DEBUG")
    async def get_state_info(self) -> Dict:
        """
        Get comprehensive state information.
        
        Returns:
            Dict containing current state and related info
        """
        with self._lock:
            return {
                "current_state": self._current_state.value,
                "last_dtmf": self._last_dtmf,
                "error_condition": self._error_condition,
                "call_info": {
                    "start_time": self._call_info.start_time.isoformat() if self._call_info.start_time else None,
                    "end_time": self._call_info.end_time.isoformat() if self._call_info.end_time else None,
                    "remote_party": self._call_info.remote_party,
                    "direction": self._call_info.direction,
                    "call_id": self._call_info.call_id
                } if self._call_info else None,
                "stats": self._stats,
                "last_transitions": self._state_history[-5:]  # Last 5 transitions
            }

    async def clear_error(self) -> None:
        """Clear error state and return to on_hook"""
        with self._lock:
            if self._current_state == PhoneState.ERROR:
                self._error_condition = None
                await self.transition_to(PhoneState.ON_HOOK)
                logger.info("Error state cleared")

# Example usage:
"""
# Get state manager instance
state_manager = StateManager()

# Subscribe to state changes
async def state_change_handler(event):
    print(f"State change: {event}")
await state_manager.subscribe(state_change_handler)

# Transition states
await state_manager.transition_to(PhoneState.RINGING)
await state_manager.transition_to(PhoneState.OFF_HOOK)
await state_manager.transition_to(PhoneState.IN_CALL, remote_party="1234567890")

# Record DTMF
await state_manager.record_dtmf("5")

# Get state info
state_info = await state_manager.get_state_info()
print(f"Current state: {state_info}")

# Handle error
await state_manager.set_error("Hardware failure")
"""