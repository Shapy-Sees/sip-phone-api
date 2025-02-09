# src/sip_phone/api/routes/status.py
"""
This module defines status and monitoring endpoints for the SIP Phone API.
These endpoints provide system health checks, metrics, and monitoring capabilities.

The endpoints integrate with the state management system to provide accurate
metrics and diagnostics about the system's operation.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, List, Optional
import psutil
import time
from datetime import datetime, timedelta

from ...core.state_manager import StateManager
from ...events.types import CallState
from ..models.phone import ErrorResponse, SystemStatus
from ...utils.logger import SIPLogger

# Configure logging with custom logger
logger = SIPLogger().get_logger(__name__)

router = APIRouter(prefix="/api/v1/status", tags=["status"])

# Dependency to get StateManager instance
async def get_state_manager() -> StateManager:
    # In a real app, you'd get this from your dependency injection system
    from ...utils.config import Config
    return StateManager(Config())

@router.get("/health", response_model=Dict[str, str])
async def health_check(
    state_manager: StateManager = Depends(get_state_manager)
) -> Dict[str, str]:
    """
    Basic health check endpoint to verify API is running.
    Includes state manager status for system health verification.
    """
    logger.debug("Health check requested")
    
    try:
        # Get debug info to verify state manager
        debug_info = await state_manager.get_debug_info()
        
        return {
            "status": "healthy",
            "state_manager": "active",
            "current_state": str(state_manager.current_state),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error("Health check failed", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Health check failed",
                code="HEALTH_CHECK_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.get("/metrics", response_model=Dict[str, Dict])
async def get_metrics(
    state_manager: StateManager = Depends(get_state_manager)
) -> Dict[str, Dict]:
    """
    Get system metrics including CPU usage, memory usage, and uptime.
    Includes application-specific metrics from state manager.
    """
    logger.debug("Metrics requested")
    
    try:
        # Get debug info for metrics
        debug_info = await state_manager.get_debug_info()
        
        # Get process info
        process = psutil.Process()
        
        metrics = {
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent,
                "uptime": int(time.time() - process.create_time())
            },
            "application": {
                "active_calls": len(state_manager.active_calls),
                "current_state": str(state_manager.current_state),
                "error_count": debug_info.get('error_count', 0),
                "state_transitions": len(debug_info.get('transition_history', [])),
                "memory_usage": process.memory_info().rss / (1024 * 1024)  # MB
            },
            "call_metrics": {
                "total_calls": len(debug_info.get('transition_history', [])),
                "active_duration": sum(
                    call.duration or 0 
                    for call in state_manager.active_calls.values()
                )
            }
        }
        return metrics
        
    except Exception as e:
        logger.error("Failed to gather metrics", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to gather metrics",
                code="METRICS_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.get("/diagnostics", response_model=Dict[str, Dict])
async def get_diagnostics(
    state_manager: StateManager = Depends(get_state_manager)
) -> Dict[str, Dict]:
    """
    Get detailed system diagnostics for troubleshooting.
    Includes state manager diagnostics and component status.
    """
    logger.debug("Diagnostics requested")
    
    try:
        # Get debug info
        debug_info = await state_manager.get_debug_info()
        
        # Get process info
        process = psutil.Process()
        
        diagnostics = {
            "state_manager": {
                "current_state": str(state_manager.current_state),
                "active_calls": len(state_manager.active_calls),
                "error_count": debug_info.get('error_count', 0),
                "persistence_path": debug_info.get('persistence_path'),
                "last_transition": debug_info.get('transition_history', [{}])[-1]
            },
            "system": {
                "cpu_count": psutil.cpu_count(),
                "memory_total": psutil.virtual_memory().total / (1024 * 1024 * 1024),  # GB
                "memory_available": psutil.virtual_memory().available / (1024 * 1024 * 1024),  # GB
                "disk_free": psutil.disk_usage('/').free / (1024 * 1024 * 1024),  # GB
                "process_memory": process.memory_info().rss / (1024 * 1024)  # MB
            },
            "network": {
                "connections": len(process.connections()),
                "network_io": process.io_counters()._asdict(),
                "sip_connection": "active",  # TODO: Get from SIP server
                "websocket_status": "running"  # TODO: Get from WebSocket manager
            },
            "hardware": {
                "ht802_status": "connected",  # TODO: Get from hardware manager
                "audio_buffer_size": 0,  # TODO: Get from audio processor
                "dtmf_detection": "active"  # TODO: Get from DTMF detector
            },
            "services": {
                "core_service": "running",
                "webhook_service": "running",
                "operator_service": "running",
                "uptime": str(timedelta(seconds=int(time.time() - process.create_time())))
            }
        }
        return diagnostics
        
    except Exception as e:
        logger.error("Failed to gather diagnostics", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to gather diagnostics",
                code="DIAGNOSTICS_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.get("/errors", response_model=List[Dict[str, str]])
async def get_recent_errors(
    limit: int = 10,
    state_manager: StateManager = Depends(get_state_manager)
) -> List[Dict[str, str]]:
    """
    Get recent error logs for monitoring and debugging.
    Retrieves errors from state manager history.
    """
    logger.debug("Recent errors requested", limit=limit)
    
    try:
        # Get debug info for error history
        debug_info = await state_manager.get_debug_info()
        
        # Get transition history errors
        errors = []
        for transition in debug_info.get('transition_history', []):
            if transition.get('to_state') == str(CallState.ERROR):
                errors.append({
                    "timestamp": transition.get('timestamp'),
                    "level": "ERROR",
                    "message": transition.get('metadata', {}).get('error', 'Unknown error'),
                    "service": "state_manager",
                    "details": str(transition.get('metadata', {}))
                })
        
        # Sort by timestamp and limit
        errors.sort(key=lambda x: x['timestamp'], reverse=True)
        return errors[:limit]
        
    except Exception as e:
        logger.error("Failed to retrieve error logs", error=str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=ErrorResponse(
                error="Failed to retrieve error logs",
                code="ERROR_LOGS_FAILED",
                details={"error": str(e)}
            ).dict()
        )
