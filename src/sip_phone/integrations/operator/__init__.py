# src/sip_phone/integrations/operator/__init__.py
"""
This module initializes the operator integration package and provides a central point
for accessing operator server functionality. It exposes the operator client and models
for use throughout the application.
"""

import logging
from typing import Optional

from ...utils.config import Config
from .client import OperatorClient, operator_client, init_operator_client
from .models import (
    OperatorStatus,
    RouteType,
    RouteRequest,
    RouteResponse,
    CallState,
    CallRequest,
    CallResponse
)

# Configure logging
logger = logging.getLogger(__name__)

class OperatorManager:
    """
    Central manager for operator server integration.
    Coordinates initialization and lifecycle of operator client.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the operator manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.client: Optional[OperatorClient] = None
    
    async def start(self) -> None:
        """
        Start the operator integration.
        """
        try:
            # Initialize operator client
            self.client = init_operator_client(self.config)
            await self.client.start()
            
            # Test connection
            status = await self.client.get_status()
            logger.info(
                f"Connected to operator server (version {status.version})"
                f" - Status: {status.status}"
            )
        except Exception as e:
            logger.error(f"Failed to start operator integration: {str(e)}")
            raise
    
    async def stop(self) -> None:
        """
        Stop the operator integration and cleanup resources.
        """
        try:
            if self.client:
                await self.client.stop()
                self.client = None
            logger.info("Operator integration stopped")
        except Exception as e:
            logger.error(f"Error stopping operator integration: {str(e)}")
            raise

# Global operator manager instance
operator_manager: Optional[OperatorManager] = None

def init_operator_manager(config: Config) -> OperatorManager:
    """
    Initialize the global operator manager instance.
    
    Args:
        config: Application configuration
        
    Returns:
        OperatorManager: The initialized operator manager
    """
    global operator_manager
    if operator_manager is None:
        operator_manager = OperatorManager(config)
    return operator_manager

# Export operator components
__all__ = [
    # Client
    "OperatorClient",
    "operator_client",
    "init_operator_client",
    
    # Models
    "OperatorStatus",
    "RouteType",
    "RouteRequest",
    "RouteResponse",
    "CallState",
    "CallRequest",
    "CallResponse",
    
    # Manager
    "OperatorManager",
    "operator_manager",
    "init_operator_manager"
]
