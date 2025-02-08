# src/sip_phone/events/dispatcher.py
"""
This module implements the event dispatch system for the SIP Phone API.
It manages event handlers and distributes events to appropriate subscribers.
"""

import logging
import asyncio
from typing import Dict, List, Set, Union, Any, Callable
from .types import (
    EventType,
    BaseEvent,
    EventHandler,
    AsyncEventHandler
)

# Configure logging
logger = logging.getLogger(__name__)

class EventDispatcher:
    """
    Central event dispatcher that manages event handlers and event distribution.
    Supports both synchronous and asynchronous event handlers.
    """
    
    def __init__(self):
        # Handler registry: event_type -> set of handlers
        self._handlers: Dict[EventType, Set[Union[EventHandler, AsyncEventHandler]]] = {}
        # Global handlers that receive all events
        self._global_handlers: Set[Union[EventHandler, AsyncEventHandler]] = set()
        # Event queue for asynchronous processing
        self._queue: asyncio.Queue[BaseEvent] = asyncio.Queue()
        # Background task for processing events
        self._process_task: Optional[asyncio.Task] = None
        # Flag to control the event processing loop
        self._running: bool = False
    
    def register_handler(
        self,
        handler: Union[EventHandler, AsyncEventHandler],
        event_types: Union[EventType, List[EventType]] = None
    ) -> None:
        """
        Register an event handler for specific event types or as a global handler.
        
        Args:
            handler: The event handler function
            event_types: Specific event type(s) to handle, or None for all events
        """
        if event_types is None:
            self._global_handlers.add(handler)
            logger.debug(f"Registered global handler: {handler.__name__}")
            return
            
        if isinstance(event_types, EventType):
            event_types = [event_types]
            
        for event_type in event_types:
            if event_type not in self._handlers:
                self._handlers[event_type] = set()
            self._handlers[event_type].add(handler)
            logger.debug(f"Registered handler {handler.__name__} for event type {event_type}")
    
    def unregister_handler(
        self,
        handler: Union[EventHandler, AsyncEventHandler],
        event_types: Union[EventType, List[EventType]] = None
    ) -> None:
        """
        Unregister an event handler.
        
        Args:
            handler: The event handler to unregister
            event_types: Event type(s) to unregister from, or None for all
        """
        if event_types is None:
            self._global_handlers.discard(handler)
            # Also remove from all specific event types
            for handlers in self._handlers.values():
                handlers.discard(handler)
            logger.debug(f"Unregistered handler {handler.__name__} from all events")
            return
            
        if isinstance(event_types, EventType):
            event_types = [event_types]
            
        for event_type in event_types:
            if event_type in self._handlers:
                self._handlers[event_type].discard(handler)
                logger.debug(f"Unregistered handler {handler.__name__} from {event_type}")
    
    async def dispatch(self, event: BaseEvent) -> None:
        """
        Dispatch an event to all registered handlers.
        
        Args:
            event: The event to dispatch
        """
        await self._queue.put(event)
        logger.debug(f"Queued event {event.type} (ID: {event.event_id})")
    
    async def start(self) -> None:
        """
        Start the event processing loop.
        """
        if self._running:
            return
            
        self._running = True
        self._process_task = asyncio.create_task(self._process_events())
        logger.info("Event dispatcher started")
    
    async def stop(self) -> None:
        """
        Stop the event processing loop.
        """
        if not self._running:
            return
            
        self._running = False
        if self._process_task:
            self._process_task.cancel()
            try:
                await self._process_task
            except asyncio.CancelledError:
                pass
        logger.info("Event dispatcher stopped")
    
    async def _process_events(self) -> None:
        """
        Main event processing loop.
        Processes events from the queue and distributes them to handlers.
        """
        while self._running:
            try:
                event = await self._queue.get()
                logger.debug(f"Processing event {event.type} (ID: {event.event_id})")
                
                # Collect all handlers for this event
                handlers = set(self._global_handlers)
                if event.type in self._handlers:
                    handlers.update(self._handlers[event.type])
                
                # Process with all handlers
                for handler in handlers:
                    try:
                        if asyncio.iscoroutinefunction(handler):
                            await handler(event)
                        else:
                            handler(event)
                    except Exception as e:
                        logger.error(f"Error in event handler {handler.__name__}: {str(e)}")
                
                self._queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {str(e)}")
    
    @property
    def queue_size(self) -> int:
        """
        Get the current size of the event queue.
        """
        return self._queue.qsize()
    
    @property
    def is_running(self) -> bool:
        """
        Check if the event dispatcher is running.
        """
        return self._running

# Global event dispatcher instance
event_dispatcher = EventDispatcher()
