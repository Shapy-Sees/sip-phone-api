# src/sip_phone/integrations/webhooks/state.py
"""
This module implements state change webhook functionality for the SIP Phone API.
It handles sending phone state change events to configured webhook endpoints.
"""

import logging
from typing import Dict, Any, Optional

from ...utils.config import Config
from .base import BaseWebhook

# Configure logging
logger = logging.getLogger(__name__)

class StateWebhook(BaseWebhook):
    """
    Webhook client for state change events.
    Handles sending phone state change notifications to configured endpoints.
    """
    
    def _get_webhook_url(self) -> str:
        """
        Get the state webhook URL from configuration.
        
        Returns:
            str: The configured webhook URL
            
        Raises:
            ValueError: If state webhook URL is not configured
        """
        url = self.config.get("state_webhook_url")
        if not url:
            raise ValueError("State webhook URL not configured")
        return url
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get headers for state webhook requests.
        Adds state-specific headers to base headers.
        
        Returns:
            dict: Headers for webhook requests
        """
        headers = super()._get_headers()
        headers.update({
            "X-Webhook-Type": "state",
            "X-State-Version": "1.0"
        })
        return headers
    
    async def send_state_change(
        self,
        previous_state: str,
        new_state: str,
        call_id: Optional[str] = None,
        reason: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send a state change event webhook.
        
        Args:
            previous_state: The previous phone state
            new_state: The new phone state
            call_id: Optional ID of the associated call
            reason: Optional reason for the state change
            metadata: Optional additional metadata about the event
        """
        data = {
            "previous_state": previous_state,
            "new_state": new_state,
            "call_id": call_id,
            "reason": reason,
            "metadata": metadata or {}
        }
        
        try:
            await self.send_webhook("state_changed", data)
            logger.info(
                f"State change webhook sent: {previous_state} -> {new_state}"
                + (f" (call: {call_id})" if call_id else "")
            )
        except Exception as e:
            logger.error(f"Failed to send state change webhook: {str(e)}")
            # Let the error propagate up for handling by caller
            raise

class StateWebhookManager:
    """
    Manager class for state webhooks.
    Handles initialization and lifecycle of state webhook clients.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the state webhook manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.webhooks: Dict[str, StateWebhook] = {}
    
    async def start(self) -> None:
        """
        Start all configured state webhook clients.
        """
        # Load webhook configurations
        webhook_configs = self.config.get("state_webhooks", [])
        
        for webhook_config in webhook_configs:
            webhook_id = webhook_config.get("id")
            if not webhook_id:
                continue
                
            try:
                webhook = StateWebhook(webhook_config)
                await webhook.start()
                self.webhooks[webhook_id] = webhook
                logger.info(f"Started state webhook client: {webhook_id}")
            except Exception as e:
                logger.error(f"Failed to start state webhook client {webhook_id}: {str(e)}")
    
    async def stop(self) -> None:
        """
        Stop all state webhook clients.
        """
        for webhook_id, webhook in self.webhooks.items():
            try:
                await webhook.stop()
                logger.info(f"Stopped state webhook client: {webhook_id}")
            except Exception as e:
                logger.error(f"Error stopping state webhook client {webhook_id}: {str(e)}")
        
        self.webhooks.clear()
    
    async def send_state_change(
        self,
        previous_state: str,
        new_state: str,
        **kwargs
    ) -> None:
        """
        Send a state change event to all configured webhooks.
        
        Args:
            previous_state: The previous phone state
            new_state: The new phone state
            **kwargs: Additional arguments to pass to send_state_change
        """
        for webhook_id, webhook in self.webhooks.items():
            try:
                await webhook.send_state_change(previous_state, new_state, **kwargs)
            except Exception as e:
                logger.error(
                    f"Failed to send state change to webhook {webhook_id}: {str(e)}"
                )

# Global state webhook manager instance
state_webhook_manager: Optional[StateWebhookManager] = None

def init_state_webhook_manager(config: Config) -> StateWebhookManager:
    """
    Initialize the global state webhook manager instance.
    
    Args:
        config: Application configuration
        
    Returns:
        StateWebhookManager: The initialized webhook manager
    """
    global state_webhook_manager
    if state_webhook_manager is None:
        state_webhook_manager = StateWebhookManager(config)
    return state_webhook_manager
