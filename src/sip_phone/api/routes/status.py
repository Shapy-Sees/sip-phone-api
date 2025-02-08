# src/sip_phone/api/routes/status.py
"""
This module defines status and monitoring endpoints for the SIP Phone API.
These endpoints provide system health checks, metrics, and monitoring capabilities.
"""

import logging
from fastapi import APIRouter, HTTPException
from typing import Dict, List
import psutil
import time

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Basic health check endpoint to verify API is running.
    """
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S")
    }

@router.get("/metrics")
async def get_metrics() -> Dict[str, Dict]:
    """
    Get system metrics including CPU usage, memory usage, and uptime.
    """
    logger.debug("Metrics requested")
    try:
        metrics = {
            "system": {
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_usage": psutil.disk_usage('/').percent
            },
            "application": {
                # TODO: Add application-specific metrics
                "active_calls": 0,
                "websocket_connections": 0,
                "errors_last_hour": 0
            }
        }
        return metrics
    except Exception as e:
        logger.error(f"Failed to gather metrics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to gather metrics")

@router.get("/diagnostics")
async def get_diagnostics() -> Dict[str, Dict]:
    """
    Get detailed system diagnostics for troubleshooting.
    """
    logger.debug("Diagnostics requested")
    try:
        diagnostics = {
            "network": {
                # TODO: Implement network diagnostics
                "sip_connection": "active",
                "websocket_status": "running",
                "last_error": None
            },
            "hardware": {
                # TODO: Implement hardware diagnostics
                "ht802_status": "connected",
                "audio_buffer_size": 0,
                "dtmf_detection": "active"
            },
            "services": {
                # TODO: Implement service status checks
                "core_service": "running",
                "webhook_service": "running",
                "operator_service": "running"
            }
        }
        return diagnostics
    except Exception as e:
        logger.error(f"Failed to gather diagnostics: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to gather diagnostics")

@router.get("/errors")
async def get_recent_errors(limit: int = 10) -> List[Dict[str, str]]:
    """
    Get recent error logs for monitoring and debugging.
    """
    logger.debug(f"Recent errors requested (limit: {limit})")
    try:
        # TODO: Implement error log retrieval from logging system
        return [
            {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "level": "ERROR",
                "message": "Example error message",
                "service": "core"
            }
        ]
    except Exception as e:
        logger.error(f"Failed to retrieve error logs: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve error logs")
