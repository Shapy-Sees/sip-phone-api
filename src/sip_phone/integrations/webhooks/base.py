# src/sip_phone/integrations/webhooks/base.py
"""
This module provides base webhook functionality for the SIP Phone API.
It defines the base webhook client and common webhook operations.
"""

import logging
import aiohttp
import json
import hmac
import hashlib
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from datetime import datetime

from ...utils.config import Config
from ...utils.errors import WebhookError

# Configure logging
logger = logging.getLogger(__name__)

class BaseWebhook(ABC):
    """
    Base class for webhook implementations.
    Provides common webhook functionality and defines the interface for specific webhooks.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the webhook client.
        
        Args:
            config: Application configuration containing webhook settings
        """
        self.config = config
        self.session: Optional[aiohttp.ClientSession] = None
        self.webhook_url = self._get_webhook_url()
        self.secret = self._get_webhook_secret()
        self.headers = self._get_headers()
        self.timeout = self.config.get("webhook_timeout", 5)
        self.max_retries = self.config.get("webhook_max_retries", 3)
    
    @abstractmethod
    def _get_webhook_url(self) -> str:
        """
        Get the webhook URL from configuration.
        Must be implemented by specific webhook classes.
        """
        pass
    
    def _get_webhook_secret(self) -> Optional[str]:
        """
        Get the webhook secret from configuration.
        Used for signing webhook payloads.
        """
        return self.config.get("webhook_secret")
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get the headers to use for webhook requests.
        Can be overridden by specific webhook classes.
        """
        return {
            "Content-Type": "application/json",
            "User-Agent": "SIPPhoneAPI/1.0"
        }
    
    def _sign_payload(self, payload: Dict[str, Any]) -> str:
        """
        Sign the webhook payload using the webhook secret.
        
        Args:
            payload: The webhook payload to sign
            
        Returns:
            str: The signature for the payload
        """
        if not self.secret:
            return ""
            
        payload_str = json.dumps(payload, sort_keys=True)
        signature = hmac.new(
            self.secret.encode(),
            payload_str.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    def _prepare_payload(self, event_type: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepare the webhook payload with common fields.
        
        Args:
            event_type: Type of event being sent
            data: Event-specific data
            
        Returns:
            dict: The prepared webhook payload
        """
        payload = {
            "event_type": event_type,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }
        
        if self.secret:
            payload["signature"] = self._sign_payload(payload)
        
        return payload
    
    async def start(self):
        """
        Initialize the webhook client.
        """
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers=self.headers,
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        logger.info(f"Webhook client started: {self.__class__.__name__}")
    
    async def stop(self):
        """
        Cleanup webhook client resources.
        """
        if self.session:
            await self.session.close()
            self.session = None
        logger.info(f"Webhook client stopped: {self.__class__.__name__}")
    
    async def send_webhook(
        self,
        event_type: str,
        data: Dict[str, Any],
        retry_count: int = 0
    ) -> None:
        """
        Send a webhook with retry logic.
        
        Args:
            event_type: Type of event being sent
            data: Event-specific data
            retry_count: Current retry attempt number
        
        Raises:
            WebhookError: If webhook delivery fails after all retries
        """
        if not self.session:
            raise WebhookError("Webhook client not started")
            
        payload = self._prepare_payload(event_type, data)
        
        try:
            async with self.session.post(
                self.webhook_url,
                json=payload
            ) as response:
                if response.status >= 400:
                    content = await response.text()
                    raise WebhookError(
                        f"Webhook delivery failed: {response.status} - {content}"
                    )
                    
                logger.debug(
                    f"Webhook delivered successfully: {event_type} to {self.webhook_url}"
                )
                
        except Exception as e:
            if retry_count < self.max_retries:
                logger.warning(
                    f"Webhook delivery failed, retrying ({retry_count + 1}/{self.max_retries})"
                )
                await self.send_webhook(event_type, data, retry_count + 1)
            else:
                logger.error(f"Webhook delivery failed after {self.max_retries} retries")
                raise WebhookError(f"Webhook delivery failed: {str(e)}")
