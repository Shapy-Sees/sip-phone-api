# src/sip_phone/api/routes/phone.py
"""
This module defines the phone control endpoints for the SIP Phone API.
These endpoints handle operations like making calls, hanging up, and controlling phone state.

The endpoints integrate with the state management system to ensure proper state transitions
and event dispatching. All operations are logged with appropriate detail levels.
"""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import Dict, Optional
from datetime import datetime
import psutil
import uuid

from ...core.state_manager import StateManager, StateTransitionError
from ...events.types import CallState, EventType
from ..models.phone import (
    CallRequest, 
    PhoneResponse, 
    DTMFRequest, 
    RingRequest,
    HangupRequest,
    SystemStatus,
    ErrorResponse,
    PhoneState
)
from ...utils.logger import SIPLogger

# Configure logging with custom logger
logger = SIPLogger().get_logger(__name__)

router = APIRouter(prefix="/api/v1/phone", tags=["phone"])

# Dependency to get StateManager instance
async def get_state_manager() -> StateManager:
    # In a real app, you'd get this from your dependency injection system
    from ...utils.config import Config
    return StateManager(Config())

@router.post("/ring", response_model=PhoneResponse)
async def ring_phone(
    request: RingRequest,
    state_manager: StateManager = Depends(get_state_manager)
) -> PhoneResponse:
    """
    Trigger the phone to ring with specified pattern and duration.
    """
    logger.info("Ring request received", duration=request.duration, pattern=request.pattern)
    
    try:
        # Only allow ringing if phone is on hook
        if state_manager.current_state != CallState.ON_HOOK:
            raise StateTransitionError("Can only ring phone when on hook")
            
        # Transition to ringing state
        await state_manager.transition_to(
            CallState.RINGING,
            metadata={
                "duration": request.duration,
                "pattern": request.pattern
            }
        )
        
        # TODO: Implement actual ring logic with PhoneController
        
        return PhoneResponse(
            status="success",
            message="Phone ringing",
            timestamp=datetime.utcnow()
        )
        
    except StateTransitionError as e:
        logger.warning("Invalid ring request", error=str(e))
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="Invalid ring request",
                code="INVALID_STATE",
                details={"current_state": state_manager.current_state}
            ).dict()
        )
    except Exception as e:
        logger.error("Ring request failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to ring phone",
                code="RING_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.post("/call", response_model=PhoneResponse)
async def make_call(
    call_request: CallRequest,
    state_manager: StateManager = Depends(get_state_manager)
) -> PhoneResponse:
    """
    Initiate a phone call to the specified number.
    """
    logger.info("Call request received", 
                number=call_request.number,
                caller_id=call_request.caller_id)
    
    try:
        # Generate unique call ID
        call_id = str(uuid.uuid4())
        
        # Start tracking call
        await state_manager.start_call(
            call_id=call_id,
            remote_uri=f"sip:{call_request.number}@domain"
        )
        
        # TODO: Implement actual call logic with PhoneController
        
        return PhoneResponse(
            status="success",
            message=f"Call initiated to {call_request.number}",
            timestamp=datetime.utcnow()
        )
        
    except StateTransitionError as e:
        logger.warning("Invalid call request", error=str(e))
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="Invalid call request",
                code="INVALID_STATE",
                details={"current_state": state_manager.current_state}
            ).dict()
        )
    except Exception as e:
        logger.error("Call request failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to initiate call",
                code="CALL_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.post("/hangup", response_model=PhoneResponse)
async def hang_up(
    request: HangupRequest,
    state_manager: StateManager = Depends(get_state_manager)
) -> PhoneResponse:
    """
    End the current call.
    """
    logger.info("Hangup request received", force=request.force)
    
    try:
        current_state = state_manager.current_state
        
        # Check if hangup is valid
        if current_state == CallState.ON_HOOK and not request.force:
            raise StateTransitionError("Phone is already on hook")
        
        # End all active calls
        for call_id in list(state_manager.active_calls.keys()):
            await state_manager.end_call(call_id)
            
        # Ensure we're back on hook
        if current_state != CallState.ON_HOOK:
            await state_manager.transition_to(
                CallState.ON_HOOK,
                metadata={"forced": request.force}
            )
        
        # TODO: Implement actual hangup logic with PhoneController
        
        return PhoneResponse(
            status="success",
            message="Call ended",
            timestamp=datetime.utcnow()
        )
        
    except StateTransitionError as e:
        logger.warning("Invalid hangup request", error=str(e))
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="Invalid hangup request",
                code="INVALID_STATE",
                details={"current_state": state_manager.current_state}
            ).dict()
        )
    except Exception as e:
        logger.error("Hangup request failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to hang up",
                code="HANGUP_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.post("/dtmf", response_model=PhoneResponse)
async def send_dtmf(
    dtmf_request: DTMFRequest,
    state_manager: StateManager = Depends(get_state_manager)
) -> PhoneResponse:
    """
    Send DTMF tones during an active call.
    """
    logger.info("DTMF request received", 
                digits=dtmf_request.digits,
                duration=dtmf_request.duration)
    
    try:
        # Verify we have an active call
        if not state_manager.active_calls:
            raise StateTransitionError("No active call to send DTMF tones")
            
        # Get first active call
        call_id = next(iter(state_manager.active_calls.keys()))
        
        # Update call metadata with DTMF
        await state_manager.update_call_metadata(
            call_id=call_id,
            dtmf=dtmf_request.digits
        )
        
        # TODO: Implement actual DTMF sending logic with PhoneController
        
        return PhoneResponse(
            status="success",
            message=f"DTMF tones sent: {dtmf_request.digits}",
            timestamp=datetime.utcnow()
        )
        
    except StateTransitionError as e:
        logger.warning("Invalid DTMF request", error=str(e))
        raise HTTPException(
            status_code=400,
            detail=ErrorResponse(
                error="Invalid DTMF request",
                code="INVALID_STATE",
                details={"current_state": state_manager.current_state}
            ).dict()
        )
    except Exception as e:
        logger.error("DTMF request failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to send DTMF tones",
                code="DTMF_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.get("/status", response_model=SystemStatus)
async def get_status(
    state_manager: StateManager = Depends(get_state_manager)
) -> SystemStatus:
    """
    Get detailed system status including phone state and health metrics.
    """
    logger.info("Status request received")
    
    try:
        # Get debug info from state manager
        debug_info = await state_manager.get_debug_info()
        
        # Get system metrics
        process = psutil.Process()
        memory_info = process.memory_info()
        cpu_percent = process.cpu_percent()
        
        # Build status response
        return SystemStatus(
            state=PhoneState(state_manager.current_state),
            uptime=int(process.create_time()),
            memory_usage=memory_info.rss / psutil.virtual_memory().total * 100,
            cpu_usage=cpu_percent,
            active_calls=len(state_manager.active_calls),
            errors=debug_info.get('error_count', 0),
            components={
                "state_manager": True,
                "sip_server": True,  # TODO: Get actual component status
                "audio_processor": True
            }
        )
        
    except Exception as e:
        logger.error("Status request failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to get system status",
                code="STATUS_FAILED",
                details={"error": str(e)}
            ).dict()
        )
