# src/sip_phone/integrations/__init__.py
"""
This module initializes the integrations package and provides a central point for
accessing external integrations. It coordinates initialization and lifecycle of
webhook and operator server integrations.
"""

import logging
from typing import Optional

from ..utils.config import Config
from .webhooks import (
    WebhookManager,
    webhook_manager,
    init_webhook_manager,
    DTMFWebhook,
    StateWebhook
)
from .operator import (
    OperatorManager,
    operator_manager,
    init_operator_manager,
    OperatorClient,
    RouteType,
    CallState
)

# Configure logging
logger = logging.getLogger(__name__)

class IntegrationsManager:
    """
    Central manager for all external integrations.
    Coordinates initialization and lifecycle of integration components.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the integrations manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.webhook_manager: Optional[WebhookManager] = None
        self.operator_manager: Optional[OperatorManager] = None
    
    async def start(self) -> None:
        """
        Start all integrations.
        """
        try:
            # Initialize webhook manager
            self.webhook_manager = init_webhook_manager(self.config)
            await self.webhook_manager.start()
            
            # Initialize operator manager
            self.operator_manager = init_operator_manager(self.config)
            await self.operator_manager.start()
            
            logger.info("All integrations started successfully")
        except Exception as e:
            logger.error(f"Failed to start integrations: {str(e)}")
            # Attempt cleanup of any started integrations
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """
        Stop all integrations and cleanup resources.
        """
        try:
            # Stop webhook manager
            if self.webhook_manager:
                await self.webhook_manager.stop()
                self.webhook_manager = None
            
            # Stop operator manager
            if self.operator_manager:
                await self.operator_manager.stop()
                self.operator_manager = None
            
            logger.info("All integrations stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping integrations: {str(e)}")
            raise

# Global integrations manager instance
integrations_manager: Optional[IntegrationsManager] = None

def init_integrations(config: Config) -> IntegrationsManager:
    """
    Initialize the global integrations manager instance.
    
    Args:
        config: Application configuration
        
    Returns:
        IntegrationsManager: The initialized integrations manager
    """
    global integrations_manager
    if integrations_manager is None:
        integrations_manager = IntegrationsManager(config)
    return integrations_manager

# Export integration components
__all__ = [
    # Webhook components
    "WebhookManager",
    "webhook_manager",
    "init_webhook_manager",
    "DTMFWebhook",
    "StateWebhook",
    
    # Operator components
    "OperatorManager",
    "operator_manager",
    "init_operator_manager",
    "OperatorClient",
    "RouteType",
    "CallState",
    
    # Central manager
    "IntegrationsManager",
    "integrations_manager",
    "init_integrations"
]
