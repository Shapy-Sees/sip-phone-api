# src/sip_phone/integrations/operator/client.py
"""
This module implements the operator server client for the SIP Phone API.
It handles communication with the operator server for call routing and control.
"""

import logging
import aiohttp
import json
from typing import Dict, Any, Optional, List
from datetime import datetime

from ...utils.config import Config
from ...utils.errors import OperatorError
from .models import (
    CallRequest,
    CallResponse,
    OperatorStatus,
    RouteRequest,
    RouteResponse
)

# Configure logging
logger = logging.getLogger(__name__)

class OperatorClient:
    """
    Client for interacting with the operator server.
    Handles API calls and maintains connection state.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the operator client.
        
        Args:
            config: Application configuration containing operator settings
        """
        self.config = config
        self.base_url = self._get_base_url()
        self.api_key = self._get_api_key()
        self.session: Optional[aiohttp.ClientSession] = None
        self.timeout = self.config.get("operator_timeout", 5)
        self.max_retries = self.config.get("operator_max_retries", 3)
    
    def _get_base_url(self) -> str:
        """
        Get the operator server base URL from configuration.
        
        Returns:
            str: The configured base URL
            
        Raises:
            ValueError: If operator URL is not configured
        """
        url = self.config.get("operator_url")
        if not url:
            raise ValueError("Operator server URL not configured")
        return url.rstrip("/")
    
    def _get_api_key(self) -> str:
        """
        Get the operator server API key from configuration.
        
        Returns:
            str: The configured API key
            
        Raises:
            ValueError: If API key is not configured
        """
        api_key = self.config.get("operator_api_key")
        if not api_key:
            raise ValueError("Operator server API key not configured")
        return api_key
    
    def _get_headers(self) -> Dict[str, str]:
        """
        Get the headers to use for operator API requests.
        
        Returns:
            dict: Headers for API requests
        """
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            "User-Agent": "SIPPhoneAPI/1.0"
        }
    
    async def start(self):
        """
        Initialize the operator client.
        """
        if not self.session:
            self.session = aiohttp.ClientSession(
                headers=self._get_headers(),
                timeout=aiohttp.ClientTimeout(total=self.timeout)
            )
        logger.info("Operator client started")
    
    async def stop(self):
        """
        Cleanup operator client resources.
        """
        if self.session:
            await self.session.close()
            self.session = None
        logger.info("Operator client stopped")
    
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        retry_count: int = 0
    ) -> Dict[str, Any]:
        """
        Make an HTTP request to the operator server.
        
        Args:
            method: HTTP method to use
            endpoint: API endpoint to call
            data: Optional request data
            retry_count: Current retry attempt number
            
        Returns:
            dict: Response data from the operator server
            
        Raises:
            OperatorError: If the request fails
        """
        if not self.session:
            raise OperatorError("Operator client not started")
            
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        try:
            async with self.session.request(method, url, json=data) as response:
                if response.status >= 400:
                    content = await response.text()
                    raise OperatorError(
                        f"Operator request failed: {response.status} - {content}"
                    )
                    
                return await response.json()
                
        except Exception as e:
            if retry_count < self.max_retries:
                logger.warning(
                    f"Operator request failed, retrying ({retry_count + 1}/{self.max_retries})"
                )
                return await self._make_request(method, endpoint, data, retry_count + 1)
            else:
                logger.error(f"Operator request failed after {self.max_retries} retries")
                raise OperatorError(f"Operator request failed: {str(e)}")
    
    async def get_status(self) -> OperatorStatus:
        """
        Get the current status of the operator server.
        
        Returns:
            OperatorStatus: Current operator server status
        """
        data = await self._make_request("GET", "/status")
        return OperatorStatus(**data)
    
    async def get_route(self, request: RouteRequest) -> RouteResponse:
        """
        Get routing information for a call.
        
        Args:
            request: Route request details
            
        Returns:
            RouteResponse: Routing information for the call
        """
        data = await self._make_request("POST", "/route", request.dict())
        return RouteResponse(**data)
    
    async def notify_call_start(self, request: CallRequest) -> CallResponse:
        """
        Notify the operator server about a new call.
        
        Args:
            request: Call details
            
        Returns:
            CallResponse: Response from the operator server
        """
        data = await self._make_request("POST", "/calls", request.dict())
        return CallResponse(**data)
    
    async def notify_call_end(
        self,
        call_id: str,
        duration: int,
        end_reason: str
    ) -> CallResponse:
        """
        Notify the operator server about a call ending.
        
        Args:
            call_id: ID of the call that ended
            duration: Duration of the call in seconds
            end_reason: Reason the call ended
            
        Returns:
            CallResponse: Response from the operator server
        """
        data = {
            "duration": duration,
            "end_reason": end_reason,
            "end_time": datetime.utcnow().isoformat()
        }
        endpoint = f"/calls/{call_id}/end"
        response_data = await self._make_request("POST", endpoint, data)
        return CallResponse(**response_data)

# Global operator client instance
operator_client: Optional[OperatorClient] = None

def init_operator_client(config: Config) -> OperatorClient:
    """
    Initialize the global operator client instance.
    
    Args:
        config: Application configuration
        
    Returns:
        OperatorClient: The initialized operator client
    """
    global operator_client
    if operator_client is None:
        operator_client = OperatorClient(config)
    return operator_client
