# src/sip_phone/events/handlers/webhook.py
"""
This module implements the webhook event handler for the SIP Phone API.
It handles dispatching events to configured webhook endpoints.
"""

import logging
import aiohttp
import json
from typing import Dict, List, Optional
from datetime import datetime

from ...utils.config import Config
from ..types import (
    BaseEvent,
    EventType,
    CallEvent,
    DTMFEvent,
    StateEvent
)

# Configure logging
logger = logging.getLogger(__name__)

class WebhookHandler:
    """
    Handles dispatching events to configured webhook endpoints.
    Supports multiple webhook configurations with event filtering.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.webhook_configs = self._load_webhook_configs()
        self.session: Optional[aiohttp.ClientSession] = None
    
    def _load_webhook_configs(self) -> List[Dict]:
        """
        Load webhook configurations from the config file.
        Each webhook config specifies URL, events to forward, and optional auth.
        """
        webhooks = self.config.get("webhooks", [])
        logger.info(f"Loaded {len(webhooks)} webhook configurations")
        return webhooks
    
    async def start(self):
        """
        Initialize the webhook handler.
        """
        if not self.session:
            self.session = aiohttp.ClientSession()
        logger.info("Webhook handler started")
    
    async def stop(self):
        """
        Cleanup resources used by the webhook handler.
        """
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("Webhook handler stopped")
    
    def _should_forward_event(self, event: BaseEvent, webhook_config: Dict) -> bool:
        """
        Check if an event should be forwarded to a webhook based on its configuration.
        
        Args:
            event: The event to check
            webhook_config: The webhook configuration
            
        Returns:
            bool: True if the event should be forwarded
        """
        # Check if webhook is enabled
        if not webhook_config.get("enabled", True):
            return False
            
        # Check event type filtering
        allowed_events = webhook_config.get("events", ["*"])
        if "*" in allowed_events:
            return True
            
        return str(event.type) in allowed_events
    
    def _prepare_payload(self, event: BaseEvent, webhook_config: Dict) -> Dict:
        """
        Prepare the webhook payload from an event.
        
        Args:
            event: The event to convert
            webhook_config: The webhook configuration
            
        Returns:
            dict: The prepared webhook payload
        """
        # Base payload with common fields
        payload = {
            "event_type": str(event.type),
            "timestamp": datetime.utcnow().isoformat(),
            "event_id": event.event_id,
            "metadata": event.metadata
        }
        
        # Add event-specific data
        if isinstance(event, CallEvent):
            payload.update({
                "call_id": event.call_id,
                "phone_number": event.phone_number,
                "duration": event.duration,
                "error": event.error
            })
        elif isinstance(event, DTMFEvent):
            payload.update({
                "digits": event.digits,
                "call_id": event.call_id,
                "duration": event.duration,
                "confidence": event.confidence
            })
        elif isinstance(event, StateEvent):
            payload.update({
                "previous_state": event.previous_state,
                "new_state": event.new_state,
                "call_id": event.call_id,
                "reason": event.reason
            })
        
        return payload
    
    async def handle_event(self, event: BaseEvent) -> None:
        """
        Handle an event by forwarding it to configured webhooks.
        
        Args:
            event: The event to handle
        """
        if not self.session:
            logger.error("Webhook handler not started")
            return
            
        for webhook_config in self.webhook_configs:
            if not self._should_forward_event(event, webhook_config):
                continue
                
            url = webhook_config["url"]
            headers = webhook_config.get("headers", {})
            
            # Add authentication if configured
            auth = webhook_config.get("auth")
            if auth:
                if auth["type"] == "bearer":
                    headers["Authorization"] = f"Bearer {auth['token']}"
                elif auth["type"] == "basic":
                    headers["Authorization"] = f"Basic {auth['token']}"
            
            # Prepare and send the webhook
            try:
                payload = self._prepare_payload(event, webhook_config)
                
                async with self.session.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=webhook_config.get("timeout", 5)
                ) as response:
                    if response.status >= 400:
                        content = await response.text()
                        logger.error(
                            f"Webhook delivery failed: {response.status} - {content}"
                        )
                    else:
                        logger.debug(
                            f"Webhook delivered successfully: {event.type} to {url}"
                        )
                        
            except Exception as e:
                logger.error(f"Error delivering webhook: {str(e)}")

# Global webhook handler instance
webhook_handler: Optional[WebhookHandler] = None

def init_webhook_handler(config: Config) -> WebhookHandler:
    """
    Initialize the global webhook handler instance.
    """
    global webhook_handler
    if webhook_handler is None:
        webhook_handler = WebhookHandler(config)
    return webhook_handler
