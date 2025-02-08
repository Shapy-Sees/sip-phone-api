# src/sip_phone/integrations/webhooks/__init__.py
"""
This module initializes the webhooks package and provides a central point for accessing
webhook functionality. It exposes webhook clients and managers for different types of
webhook integrations.
"""

import logging
from typing import Optional

from ...utils.config import Config
from .base import BaseWebhook
from .dtmf import DTMFWebhook, DTMFWebhookManager, init_dtmf_webhook_manager
from .state import StateWebhook, StateWebhookManager, init_state_webhook_manager

# Configure logging
logger = logging.getLogger(__name__)

class WebhookManager:
    """
    Central manager for all webhook functionality.
    Coordinates initialization and lifecycle of different webhook types.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the webhook manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.dtmf_manager: Optional[DTMFWebhookManager] = None
        self.state_manager: Optional[StateWebhookManager] = None
    
    async def start(self) -> None:
        """
        Start all webhook managers and initialize webhook clients.
        """
        try:
            # Initialize DTMF webhook manager
            self.dtmf_manager = init_dtmf_webhook_manager(self.config)
            await self.dtmf_manager.start()
            
            # Initialize state webhook manager
            self.state_manager = init_state_webhook_manager(self.config)
            await self.state_manager.start()
            
            logger.info("Webhook manager started successfully")
        except Exception as e:
            logger.error(f"Failed to start webhook manager: {str(e)}")
            raise
    
    async def stop(self) -> None:
        """
        Stop all webhook managers and cleanup resources.
        """
        try:
            # Stop DTMF webhook manager
            if self.dtmf_manager:
                await self.dtmf_manager.stop()
            
            # Stop state webhook manager
            if self.state_manager:
                await self.state_manager.stop()
            
            logger.info("Webhook manager stopped successfully")
        except Exception as e:
            logger.error(f"Error stopping webhook manager: {str(e)}")
            raise

# Global webhook manager instance
webhook_manager: Optional[WebhookManager] = None

def init_webhook_manager(config: Config) -> WebhookManager:
    """
    Initialize the global webhook manager instance.
    
    Args:
        config: Application configuration
        
    Returns:
        WebhookManager: The initialized webhook manager
    """
    global webhook_manager
    if webhook_manager is None:
        webhook_manager = WebhookManager(config)
    return webhook_manager

# Export webhook components
__all__ = [
    # Base webhook
    "BaseWebhook",
    
    # DTMF webhooks
    "DTMFWebhook",
    "DTMFWebhookManager",
    "init_dtmf_webhook_manager",
    
    # State webhooks
    "StateWebhook",
    "StateWebhookManager",
    "init_state_webhook_manager",
    
    # Central manager
    "WebhookManager",
    "webhook_manager",
    "init_webhook_manager"
]
