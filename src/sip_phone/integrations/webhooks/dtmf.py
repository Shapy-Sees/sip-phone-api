# src/sip_phone/integrations/webhooks/dtmf.py
"""
This module implements DTMF-specific webhook functionality for the SIP Phone API.
It handles sending DTMF detection events to configured webhook endpoints.
"""

import logging
from typing import Dict, Any, Optional

from ...utils.config import Config
from .base import BaseWebhook

# Configure logging
logger = logging.getLogger(__name__)

class DTMFWebhook(BaseWebhook):
    """
    Webhook client for DTMF-related events.
    Handles sending DTMF detection notifications to configured endpoints.
    """
    
    def _get_webhook_url(self) -> str:
        """
        Get the DTMF webhook URL from configuration.
        
        Returns:
            str: The configured webhook URL
            
        Raises:
            ValueError: If DTMF webhook URL is not configured
        """
        url = self.config.get("dtmf_webhook_url")
        if not url:
            raise ValueError("DTMF webhook URL not configured")
        return url
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get headers for DTMF webhook requests.
        Adds DTMF-specific headers to base headers.
        
        Returns:
            dict: Headers for webhook requests
        """
        headers = super()._get_headers()
        headers.update({
            "X-Webhook-Type": "dtmf",
            "X-DTMF-Version": "1.0"
        })
        return headers
    
    async def send_dtmf_event(
        self,
        digits: str,
        call_id: str,
        confidence: Optional[float] = None,
        duration: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Send a DTMF detection event webhook.
        
        Args:
            digits: The detected DTMF digits
            call_id: ID of the call where DTMF was detected
            confidence: Optional confidence score of the detection
            duration: Optional duration of the DTMF tone in milliseconds
            metadata: Optional additional metadata about the event
        """
        data = {
            "digits": digits,
            "call_id": call_id,
            "confidence": confidence,
            "duration": duration,
            "metadata": metadata or {}
        }
        
        try:
            await self.send_webhook("dtmf_detected", data)
            logger.info(f"DTMF webhook sent: {digits} (call: {call_id})")
        except Exception as e:
            logger.error(f"Failed to send DTMF webhook: {str(e)}")
            # Let the error propagate up for handling by caller
            raise

class DTMFWebhookManager:
    """
    Manager class for DTMF webhooks.
    Handles initialization and lifecycle of DTMF webhook clients.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the DTMF webhook manager.
        
        Args:
            config: Application configuration
        """
        self.config = config
        self.webhooks: Dict[str, DTMFWebhook] = {}
    
    async def start(self) -> None:
        """
        Start all configured DTMF webhook clients.
        """
        # Load webhook configurations
        webhook_configs = self.config.get("dtmf_webhooks", [])
        
        for webhook_config in webhook_configs:
            webhook_id = webhook_config.get("id")
            if not webhook_id:
                continue
                
            try:
                webhook = DTMFWebhook(webhook_config)
                await webhook.start()
                self.webhooks[webhook_id] = webhook
                logger.info(f"Started DTMF webhook client: {webhook_id}")
            except Exception as e:
                logger.error(f"Failed to start DTMF webhook client {webhook_id}: {str(e)}")
    
    async def stop(self) -> None:
        """
        Stop all DTMF webhook clients.
        """
        for webhook_id, webhook in self.webhooks.items():
            try:
                await webhook.stop()
                logger.info(f"Stopped DTMF webhook client: {webhook_id}")
            except Exception as e:
                logger.error(f"Error stopping DTMF webhook client {webhook_id}: {str(e)}")
        
        self.webhooks.clear()
    
    async def send_dtmf_event(
        self,
        digits: str,
        call_id: str,
        **kwargs
    ) -> None:
        """
        Send a DTMF event to all configured webhooks.
        
        Args:
            digits: The detected DTMF digits
            call_id: ID of the call where DTMF was detected
            **kwargs: Additional arguments to pass to send_dtmf_event
        """
        for webhook_id, webhook in self.webhooks.items():
            try:
                await webhook.send_dtmf_event(digits, call_id, **kwargs)
            except Exception as e:
                logger.error(
                    f"Failed to send DTMF event to webhook {webhook_id}: {str(e)}"
                )

# Global DTMF webhook manager instance
dtmf_webhook_manager: Optional[DTMFWebhookManager] = None

def init_dtmf_webhook_manager(config: Config) -> DTMFWebhookManager:
    """
    Initialize the global DTMF webhook manager instance.
    
    Args:
        config: Application configuration
        
    Returns:
        DTMFWebhookManager: The initialized webhook manager
    """
    global dtmf_webhook_manager
    if dtmf_webhook_manager is None:
        dtmf_webhook_manager = DTMFWebhookManager(config)
    return dtmf_webhook_manager
