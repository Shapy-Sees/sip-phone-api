# src/sip_phone/api/routes/webhooks.py
"""
This module defines webhook endpoints for the SIP Phone API.
These endpoints handle incoming webhooks from external services and integration callbacks.

The endpoints integrate with the event system to dispatch incoming webhooks to appropriate
handlers and maintain state consistency through the state management system.
"""

from fastapi import APIRouter, HTTPException, Request, Depends, BackgroundTasks, Query
from typing import Dict, Any, List, Optional
from datetime import datetime

from ...events.dispatcher import event_dispatcher
from ...events.types import WebhookEvent, EventType
from ...core.state_manager import StateManager
from ..models.webhooks import (
    DTMFWebhook,
    StateChangeWebhook,
    OperatorWebhook,
    WebhookResponse,
    WebhookError
)
from ...utils.logger import get_logger
from ...integrations.webhooks.delivery import (
    WebhookDeliveryManager,
    WebhookDeliveryStatus,
    init_delivery_manager
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])

# Dependency to get StateManager instance
async def get_state_manager() -> StateManager:
    # In a real app, you'd get this from your dependency injection system
    from ...utils.config import Config
    return StateManager(Config())

@router.post("/dtmf", response_model=WebhookResponse)
async def dtmf_webhook(
    webhook: DTMFWebhook,
    background_tasks: BackgroundTasks,
    state_manager: StateManager = Depends(get_state_manager)
) -> WebhookResponse:
    """
    Handle incoming DTMF webhook notifications.
    Updates call metadata and dispatches DTMF events.
    """
    logger.info("Received DTMF webhook", 
                digits=webhook.digits,
                call_id=webhook.call_id)
    
    try:
        # Update call metadata with DTMF
        if webhook.call_id:
            background_tasks.add_task(
                state_manager.update_call_metadata,
                call_id=webhook.call_id,
                dtmf=webhook.digits
            )
        
        # Create and dispatch event
        event = WebhookEvent(
            type=EventType.DTMF,
            call_id=webhook.call_id,
            timestamp=webhook.timestamp or datetime.utcnow().isoformat(),
            metadata={
                "digits": webhook.digits,
                "duration": webhook.duration
            }
        )
        background_tasks.add_task(event_dispatcher.dispatch, event)
        
        return WebhookResponse(
            status="success",
            message="DTMF webhook processed",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error("Failed to process DTMF webhook", 
                    error=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=WebhookError(
                error="Failed to process DTMF webhook",
                code="DTMF_WEBHOOK_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.post("/state-change", response_model=WebhookResponse)
async def state_change_webhook(
    webhook: StateChangeWebhook,
    background_tasks: BackgroundTasks,
    state_manager: StateManager = Depends(get_state_manager)
) -> WebhookResponse:
    """
    Handle incoming state change webhook notifications.
    Updates system state and dispatches state change events.
    """
    logger.info("Received state change webhook",
                previous_state=webhook.previous_state,
                new_state=webhook.new_state)
    
    try:
        # Transition to new state if provided
        if webhook.new_state:
            background_tasks.add_task(
                state_manager.transition_to,
                new_state=webhook.new_state,
                metadata={
                    "source": "webhook",
                    "previous_state": webhook.previous_state,
                    "reason": webhook.reason
                }
            )
        
        # Create and dispatch event
        event = WebhookEvent(
            type=EventType.STATE_CHANGE,
            call_id=webhook.call_id,
            timestamp=webhook.timestamp or datetime.utcnow().isoformat(),
            metadata={
                "previous_state": webhook.previous_state,
                "new_state": webhook.new_state,
                "reason": webhook.reason
            }
        )
        background_tasks.add_task(event_dispatcher.dispatch, event)
        
        return WebhookResponse(
            status="success",
            message="State change webhook processed",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error("Failed to process state change webhook",
                    error=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=WebhookError(
                error="Failed to process state change webhook",
                code="STATE_CHANGE_WEBHOOK_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.post("/operator", response_model=WebhookResponse)
async def operator_webhook(
    webhook: OperatorWebhook,
    background_tasks: BackgroundTasks,
    state_manager: StateManager = Depends(get_state_manager)
) -> WebhookResponse:
    """
    Handle incoming webhooks from the operator service.
    Processes operator commands and updates system state.
    """
    logger.info("Received operator webhook",
                action=webhook.action,
                call_id=webhook.call_id)
    
    try:
        # Handle operator action
        if webhook.action == "hangup":
            background_tasks.add_task(
                state_manager.end_call,
                call_id=webhook.call_id
            )
        elif webhook.action == "mute":
            background_tasks.add_task(
                state_manager.update_call_metadata,
                call_id=webhook.call_id,
                custom_data={"muted": True}
            )
        
        # Create and dispatch event
        event = WebhookEvent(
            type=EventType.OPERATOR,
            call_id=webhook.call_id,
            timestamp=webhook.timestamp or datetime.utcnow().isoformat(),
            metadata={
                "action": webhook.action,
                "params": webhook.params
            }
        )
        background_tasks.add_task(event_dispatcher.dispatch, event)
        
        return WebhookResponse(
            status="success",
            message=f"Operator webhook processed: {webhook.action}",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error("Failed to process operator webhook",
                    error=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=WebhookError(
                error="Failed to process operator webhook",
                code="OPERATOR_WEBHOOK_FAILED",
                details={"error": str(e)}
            ).dict()
        )

# Dependency to get DeliveryManager instance
async def get_delivery_manager() -> WebhookDeliveryManager:
    # In a real app, you'd get this from your dependency injection system
    delivery_manager = init_delivery_manager()
    if not delivery_manager._running:
        await delivery_manager.start()
    return delivery_manager

@router.get("/status/{webhook_id}", response_model=WebhookDeliveryStatus)
async def get_webhook_status(
    webhook_id: str,
    delivery_manager: WebhookDeliveryManager = Depends(get_delivery_manager)
) -> WebhookDeliveryStatus:
    """
    Get the delivery status of a specific webhook.
    """
    status = delivery_manager.get_delivery_status(webhook_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=WebhookError(
                error="Webhook not found",
                code="WEBHOOK_NOT_FOUND",
                details={"webhook_id": webhook_id}
            ).dict()
        )
    return status

@router.get("/status", response_model=List[WebhookDeliveryStatus])
async def list_webhook_statuses(
    status: Optional[str] = Query(None, description="Filter by status (pending, success, failed, retrying)"),
    limit: int = Query(100, ge=1, le=1000),
    delivery_manager: WebhookDeliveryManager = Depends(get_delivery_manager)
) -> List[WebhookDeliveryStatus]:
    """
    List webhook delivery statuses with optional filtering.
    """
    deliveries = delivery_manager.get_pending_deliveries()
    if status:
        deliveries = [d for d in deliveries if d.status == status]
    return deliveries[:limit]

@router.post("/retry/{webhook_id}", response_model=WebhookResponse)
async def retry_webhook(
    webhook_id: str,
    delivery_manager: WebhookDeliveryManager = Depends(get_delivery_manager)
) -> WebhookResponse:
    """
    Manually retry a failed webhook delivery.
    """
    status = delivery_manager.get_delivery_status(webhook_id)
    if not status:
        raise HTTPException(
            status_code=404,
            detail=WebhookError(
                error="Webhook not found",
                code="WEBHOOK_NOT_FOUND",
                details={"webhook_id": webhook_id}
            ).dict()
        )
    
    if status.status not in ("failed", "retrying"):
        raise HTTPException(
            status_code=400,
            detail=WebhookError(
                error="Webhook cannot be retried",
                code="INVALID_RETRY",
                details={
                    "webhook_id": webhook_id,
                    "current_status": status.status
                }
            ).dict()
        )
    
    try:
        await delivery_manager.deliver(
            webhook_id=webhook_id,
            event_id=status.event_id,
            url=status.url,
            payload=status.payload
        )
        
        return WebhookResponse(
            status="success",
            message="Webhook queued for retry",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error("Failed to retry webhook",
                    webhook_id=webhook_id,
                    error=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=WebhookError(
                error="Failed to retry webhook",
                code="RETRY_FAILED",
                details={"error": str(e)}
            ).dict()
        )

@router.post("/custom/{integration_name}", response_model=WebhookResponse)
async def custom_webhook(
    integration_name: str,
    request: Request,
    background_tasks: BackgroundTasks,
    state_manager: StateManager = Depends(get_state_manager)
) -> WebhookResponse:
    """
    Handle incoming webhooks from custom integrations.
    Validates and processes custom integration payloads.
    """
    logger.info("Received custom webhook",
                integration=integration_name)
    
    try:
        # Parse and validate payload
        payload = await request.json()
        
        # Create and dispatch event
        event = WebhookEvent(
            type=EventType.CUSTOM,
            timestamp=datetime.utcnow().isoformat(),
            metadata={
                "integration": integration_name,
                "payload": payload
            }
        )
        background_tasks.add_task(event_dispatcher.dispatch, event)
        
        # Update state if needed
        if payload.get("update_state"):
            background_tasks.add_task(
                state_manager.transition_to,
                new_state=payload["update_state"],
                metadata={
                    "source": f"custom_{integration_name}",
                    "payload": payload
                }
            )
        
        return WebhookResponse(
            status="success",
            message=f"Custom webhook for {integration_name} processed",
            timestamp=datetime.utcnow()
        )
        
    except Exception as e:
        logger.error("Failed to process custom webhook",
                    integration=integration_name,
                    error=str(e),
                    exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=WebhookError(
                error=f"Failed to process {integration_name} webhook",
                code="CUSTOM_WEBHOOK_FAILED",
                details={"error": str(e)}
            ).dict()
        )
