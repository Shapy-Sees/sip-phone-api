# src/sip_phone/integrations/webhooks/delivery.py
"""
This module implements webhook delivery management with retry logic and delivery tracking.
It handles reliable delivery of webhooks with configurable retry strategies and logging.
"""

import asyncio
import logging
import time
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
import aiohttp
from pydantic import BaseModel

from ...utils.logger import get_logger
from ...api.models.webhooks import WebhookResponse, WebhookError

logger = get_logger(__name__)

class DeliveryAttempt(BaseModel):
    """
    Model to track individual webhook delivery attempts.
    """
    timestamp: datetime
    status_code: Optional[int]
    error: Optional[str]
    response: Optional[str]
    latency: float  # in milliseconds

class WebhookDeliveryStatus(BaseModel):
    """
    Model to track the delivery status of a webhook.
    """
    webhook_id: str
    event_id: str
    url: str
    created_at: datetime
    attempts: List[DeliveryAttempt]
    last_attempt: Optional[datetime]
    next_retry: Optional[datetime]
    status: str  # pending, success, failed, retrying
    max_attempts: int
    current_attempt: int
    payload: Dict[str, Any]

class RetryStrategy:
    """
    Configurable retry strategy with exponential backoff.
    """
    def __init__(
        self,
        max_attempts: int = 5,
        initial_delay: float = 1.0,
        max_delay: float = 300.0,
        backoff_factor: float = 2.0,
        jitter: bool = True
    ):
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter

    def get_next_delay(self, attempt: int) -> float:
        """
        Calculate the next retry delay with exponential backoff.
        """
        delay = min(
            self.initial_delay * (self.backoff_factor ** (attempt - 1)),
            self.max_delay
        )
        if self.jitter:
            # Add random jitter ±25%
            delay *= (0.75 + (time.time() % 0.5))
        return delay

class WebhookDeliveryManager:
    """
    Manages webhook delivery with retry logic and status tracking.
    """
    def __init__(
        self,
        retry_strategy: Optional[RetryStrategy] = None,
        session: Optional[aiohttp.ClientSession] = None
    ):
        self.retry_strategy = retry_strategy or RetryStrategy()
        self.session = session
        self.deliveries: Dict[str, WebhookDeliveryStatus] = {}
        self.retry_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._running = False
        self._retry_task: Optional[asyncio.Task] = None

    async def start(self):
        """
        Start the delivery manager and retry processor.
        """
        if self._running:
            return

        if not self.session:
            self.session = aiohttp.ClientSession()

        self._running = True
        self._retry_task = asyncio.create_task(self._process_retries())
        logger.info("Webhook delivery manager started")

    async def stop(self):
        """
        Stop the delivery manager and cleanup resources.
        """
        self._running = False
        if self._retry_task:
            self._retry_task.cancel()
            try:
                await self._retry_task
            except asyncio.CancelledError:
                pass

        if self.session:
            await self.session.close()
            self.session = None

        logger.info("Webhook delivery manager stopped")

    async def deliver(
        self,
        webhook_id: str,
        event_id: str,
        url: str,
        payload: Dict[str, Any],
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0
    ) -> WebhookDeliveryStatus:
        """
        Attempt to deliver a webhook with retry support.
        """
        delivery = WebhookDeliveryStatus(
            webhook_id=webhook_id,
            event_id=event_id,
            url=url,
            created_at=datetime.utcnow(),
            attempts=[],
            status="pending",
            max_attempts=self.retry_strategy.max_attempts,
            current_attempt=0,
            payload=payload
        )
        self.deliveries[webhook_id] = delivery

        try:
            await self._attempt_delivery(delivery, headers, timeout)
        except Exception as e:
            logger.error(f"Initial delivery attempt failed: {str(e)}")
            await self._schedule_retry(delivery)

        return delivery

    async def _attempt_delivery(
        self,
        delivery: WebhookDeliveryStatus,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0
    ) -> bool:
        """
        Make a single delivery attempt.
        """
        if not self.session:
            raise RuntimeError("Delivery manager not started")

        delivery.current_attempt += 1
        start_time = time.time()

        try:
            async with self.session.post(
                delivery.url,
                json=delivery.payload,
                headers=headers,
                timeout=timeout
            ) as response:
                latency = (time.time() - start_time) * 1000
                content = await response.text()

                attempt = DeliveryAttempt(
                    timestamp=datetime.utcnow(),
                    status_code=response.status,
                    response=content,
                    latency=latency
                )
                delivery.attempts.append(attempt)
                delivery.last_attempt = attempt.timestamp

                if response.status < 400:
                    delivery.status = "success"
                    logger.info(
                        f"Webhook {delivery.webhook_id} delivered successfully "
                        f"(attempt {delivery.current_attempt}/{delivery.max_attempts})"
                    )
                    return True
                else:
                    delivery.status = "failed" if delivery.current_attempt >= delivery.max_attempts else "retrying"
                    logger.warning(
                        f"Webhook delivery failed with status {response.status}: {content}"
                    )
                    return False

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            attempt = DeliveryAttempt(
                timestamp=datetime.utcnow(),
                error=str(e),
                latency=latency
            )
            delivery.attempts.append(attempt)
            delivery.last_attempt = attempt.timestamp
            delivery.status = "failed" if delivery.current_attempt >= delivery.max_attempts else "retrying"
            
            logger.error(f"Webhook delivery error: {str(e)}")
            return False

    async def _schedule_retry(self, delivery: WebhookDeliveryStatus):
        """
        Schedule a retry attempt if attempts remain.
        """
        if delivery.current_attempt >= delivery.max_attempts:
            delivery.status = "failed"
            logger.warning(
                f"Webhook {delivery.webhook_id} failed after {delivery.current_attempt} attempts"
            )
            return

        delay = self.retry_strategy.get_next_delay(delivery.current_attempt)
        next_attempt = datetime.utcnow() + timedelta(seconds=delay)
        delivery.next_retry = next_attempt

        # Priority queue item: (timestamp, webhook_id)
        await self.retry_queue.put((next_attempt.timestamp(), delivery.webhook_id))
        
        logger.info(
            f"Scheduled retry for webhook {delivery.webhook_id} "
            f"in {delay:.1f}s (attempt {delivery.current_attempt + 1}/{delivery.max_attempts})"
        )

    async def _process_retries(self):
        """
        Process the retry queue.
        """
        while self._running:
            try:
                # Get the next retry with timeout
                retry_time, webhook_id = await asyncio.wait_for(
                    self.retry_queue.get(),
                    timeout=1.0
                )

                # Check if it's time to retry
                now = datetime.utcnow().timestamp()
                if retry_time > now:
                    # Not yet time, put it back
                    await self.retry_queue.put((retry_time, webhook_id))
                    await asyncio.sleep(0.1)
                    continue

                # Attempt retry
                delivery = self.deliveries.get(webhook_id)
                if not delivery or delivery.status == "success":
                    continue

                success = await self._attempt_delivery(delivery)
                if not success:
                    await self._schedule_retry(delivery)

                self.retry_queue.task_done()

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing retry queue: {str(e)}")
                await asyncio.sleep(1.0)

    def get_delivery_status(self, webhook_id: str) -> Optional[WebhookDeliveryStatus]:
        """
        Get the current delivery status for a webhook.
        """
        return self.deliveries.get(webhook_id)

    def get_pending_deliveries(self) -> List[WebhookDeliveryStatus]:
        """
        Get all pending webhook deliveries.
        """
        return [
            delivery for delivery in self.deliveries.values()
            if delivery.status in ("pending", "retrying")
        ]

# Global delivery manager instance
delivery_manager: Optional[WebhookDeliveryManager] = None

def init_delivery_manager(
    retry_strategy: Optional[RetryStrategy] = None,
    session: Optional[aiohttp.ClientSession] = None
) -> WebhookDeliveryManager:
    """
    Initialize the global webhook delivery manager instance.
    """
    global delivery_manager
    if delivery_manager is None:
        delivery_manager = WebhookDeliveryManager(
            retry_strategy=retry_strategy,
            session=session
        )
    return delivery_manager
