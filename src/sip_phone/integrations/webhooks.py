# src/sip_phone/integrations/webhooks.py
"""
Webhook dispatch system for delivering DTMF events to configured endpoints.
Implements retry logic, delivery monitoring, and error handling as specified
in the architecture document.
"""

import logging
import json
import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, Optional

from ..utils.config import Config
from ..utils.errors import WebhookDeliveryError

logger = logging.getLogger(__name__)

class WebhookManager:
    def __init__(self, config: Config):
        self.config = config
        self.webhook_queue = asyncio.Queue()
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def start(self):
        """Initialize the webhook manager and start the delivery worker."""
        self.session = aiohttp.ClientSession()
        asyncio.create_task(self._delivery_worker())
        logger.info("Webhook manager started")

    async def stop(self):
        """Gracefully shut down the webhook manager."""
        if self.session:
            await self.session.close()
        logger.info("Webhook manager stopped")

    async def dispatch_dtmf(self, digit: str, call_id: str, duration_ms: int):
        """
        Queue a DTMF event for delivery to configured webhook endpoint.
        
        Args:
            digit: The DTMF digit detected
            call_id: Unique identifier for the current call
            duration_ms: Duration of the DTMF tone in milliseconds
        """
        event = {
            "type": "dtmf",
            "digit": digit,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "call_id": call_id,
            "sequence": await self._get_next_sequence(),
            "duration_ms": duration_ms
        }
        
        await self.webhook_queue.put(event)
        logger.debug(f"Queued DTMF event: {event}")

    async def _delivery_worker(self):
        """Background worker that processes the webhook queue and handles retries."""
        while True:
            try:
                event = await self.webhook_queue.get()
                await self._deliver_with_retry(event)
                self.webhook_queue.task_done()
            except Exception as e:
                logger.error(f"Error in webhook delivery worker: {e}")
                await asyncio.sleep(1)  # Prevent tight loop on persistent errors

    async def _deliver_with_retry(self, event: Dict):
        """
        Attempt to deliver a webhook with configurable retries and backoff.
        
        Args:
            event: The event payload to deliver
        """
        config = self.config.get("webhooks.dtmf", {})
        retry_count = config.get("retry_count", 3)
        retry_delay_ms = config.get("retry_delay_ms", 500)
        timeout_ms = config.get("timeout_ms", 1000)
        
        for attempt in range(retry_count + 1):
            try:
                if not self.session:
                    raise WebhookDeliveryError("HTTP session not initialized")
                    
                async with self.session.post(
                    config["url"],
                    json=event,
                    headers={"Authorization": f"Bearer {config.get('auth_token')}"},
                    timeout=timeout_ms / 1000
                ) as response:
                    if response.status < 400:
                        logger.info(f"Successfully delivered webhook: {event['type']}")
                        return
                    else:
                        raise WebhookDeliveryError(
                            f"Webhook delivery failed with status {response.status}"
                        )
                        
            except Exception as e:
                if attempt == retry_count:
                    logger.error(f"Final webhook delivery attempt failed: {e}")
                    # Could implement dead letter queue here
                    return
                    
                delay = (retry_delay_ms / 1000) * (2 ** attempt)  # Exponential backoff
                logger.warning(
                    f"Webhook delivery attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {delay:.1f}s"
                )
                await asyncio.sleep(delay)

    async def _get_next_sequence(self) -> int:
        """Get the next sequence number for DTMF events."""
        # In a production system, this would use a persistent counter
        # For now, we'll use a simple incrementing number
        if not hasattr(self, "_sequence"):
            self._sequence = 0
        self._sequence += 1
        return self._sequence
