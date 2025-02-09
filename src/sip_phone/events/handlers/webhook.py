# src/sip_phone/events/handlers/webhook.py
"""
This module implements the webhook event handler for the SIP Phone API.
It handles dispatching events to configured webhook endpoints with retry logic
and delivery tracking.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from ...utils.config import Config
from ...utils.logger import get_logger
from ..types import (
    BaseEvent,
    EventType,
    CallEvent,
    DTMFEvent,
    StateEvent,
    SystemEvent
)
from ...integrations.webhooks.delivery import (
    WebhookDeliveryManager,
    RetryStrategy,
    init_delivery_manager
)

logger = get_logger(__name__)

class WebhookHandler:
    """
    Handles dispatching events to configured webhook endpoints with retry support.
    Supports multiple webhook configurations with event filtering and authentication.
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.webhook_configs = self._load_webhook_configs()
        self.delivery_manager: Optional[WebhookDeliveryManager] = None
        
        # Configure retry strategy from config
        retry_config = config.get("webhooks", {}).get("retry", {})
        self.retry_strategy = RetryStrategy(
            max_attempts=retry_config.get("max_attempts", 5),
            initial_delay=retry_config.get("initial_delay", 1.0),
            max_delay=retry_config.get("max_delay", 300.0),
            backoff_factor=retry_config.get("backoff_factor", 2.0),
            jitter=retry_config.get("jitter", True)
        )
    
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
        Initialize the webhook handler and delivery manager.
        """
        self.delivery_manager = init_delivery_manager(
            retry_strategy=self.retry_strategy
        )
        await self.delivery_manager.start()
        logger.info("Webhook handler started")
    
    async def stop(self):
        """
        Cleanup resources used by the webhook handler.
        """
        if self.delivery_manager:
            await self.delivery_manager.stop()
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
            
        # Check event type and any subtypes
        event_type = str(event.type)
        return any(
            event_type.startswith(allowed) 
            for allowed in allowed_events
        )
    
    def _prepare_payload(self, event: BaseEvent, webhook_config: Dict) -> Dict[str, Any]:
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
                "digit": event.digit,
                "call_id": event.call_id,
                "duration": event.duration,
                "sequence": event.sequence
            })
        elif isinstance(event, StateEvent):
            payload.update({
                "previous_state": str(event.previous_state),
                "new_state": str(event.new_state),
                "call_id": event.call_id,
                "reason": event.reason
            })
        elif isinstance(event, SystemEvent):
            payload.update({
                "level": event.level,
                "component": event.component,
                "message": event.message,
                "error": event.error,
                "stack_trace": event.stack_trace
            })
        
        return payload
    
    async def handle_event(self, event: BaseEvent) -> None:
        """
        Handle an event by forwarding it to configured webhooks with retry support.
        
        Args:
            event: The event to handle
        """
        if not self.delivery_manager:
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
            
            # Generate webhook ID and prepare payload
            webhook_id = str(uuid.uuid4())
            payload = self._prepare_payload(event, webhook_config)
            
            try:
                # Attempt delivery with retry support
                delivery = await self.delivery_manager.deliver(
                    webhook_id=webhook_id,
                    event_id=event.event_id,
                    url=url,
                    payload=payload,
                    headers=headers,
                    timeout=webhook_config.get("timeout", 5.0)
                )
                
                logger.debug(
                    f"Webhook queued for delivery: {event.type} to {url} "
                    f"(ID: {webhook_id})"
                )
                
            except Exception as e:
                logger.error(
                    f"Error queueing webhook: {str(e)}",
                    extra={
                        "webhook_id": webhook_id,
                        "event_id": event.event_id,
                        "url": url
                    }
                )

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
