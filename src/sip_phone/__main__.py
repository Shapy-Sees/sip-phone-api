# src/sip_phone/__main__.py
"""
Main entry point for SIP Phone API.
Handles initialization of all components, configuration loading,
and graceful shutdown. Provides comprehensive logging of startup sequence.
"""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

from .core.sip_server import SIPServer
from .utils.config import Config, ConfigurationError
from .utils.logger import SIPLogger, LoggerConfig
from .api.server import APIServer
from .api.websocket.manager import init_connection_manager
from .events.dispatcher import EventDispatcher

async def shutdown(sip_server: Optional[SIPServer] = None,
                  api_server: Optional[APIServer] = None) -> None:
    """
    Gracefully shut down all services.
    
    Args:
        sip_server: SIP server instance
        api_server: API server instance
    """
    logger = SIPLogger().get_logger(__name__)
    logger.info("Initiating graceful shutdown")
        
    if api_server:
        logger.debug("Stopping API server")
        await api_server.stop()
        
    if sip_server:
        logger.debug("Stopping SIP server")
        await sip_server.stop()
    
    logger.info("All services stopped")

async def main() -> None:
    """
    Main application entry point.
    Initializes all services and handles graceful shutdown.
    """
    # Initialize configuration
    config = Config()
    config_path = Path(sys.argv[1] if len(sys.argv) > 1 else "/app/config/config.yml")
    
    try:
        # Load configuration
        config.load(config_path)
        
        # Initialize logger
        logger_config = LoggerConfig(
            level=config.logging.level,
            format=config.logging.format,
            output_file=config.logging.output
        )
        logger = SIPLogger()
        logger.configure(logger_config)
        
        # Get module logger
        log = logger.get_logger(__name__)
        log.info("Starting SIP Phone API",
                 config_path=str(config_path),
                 log_level=config.logging.level)
        
        # Initialize event dispatcher
        event_dispatcher = EventDispatcher()
        
        # Initialize servers
        sip_server = SIPServer(event_dispatcher)
        api_server = APIServer(sip_server)
        
        # Initialize WebSocket manager
        ws_manager = init_connection_manager(config)
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s,
                lambda s=s: asyncio.create_task(
                    shutdown(sip_server, api_server)
                )
            )
        
        # Start all services
        log.info("Starting services")
        
        # Start SIP server
        log.debug("Starting SIP server")
        await sip_server.start()
        
        # Start API server
        log.debug("Starting API server")
        await api_server.start()
        
        log.info("All services started successfully",
                 sip_port=config.sip.server.split(':')[-1],
                 api_port=config.api.port)
        
        # Keep the application running
        while True:
            await asyncio.sleep(1)
            
    except ConfigurationError as e:
        log.error("Configuration error",
                 error=str(e),
                 config_path=str(config_path))
        sys.exit(1)
    except Exception as e:
        log.error("Unexpected error during startup",
                 error=str(e),
                 exc_info=True)
        sys.exit(1)
    finally:
        log.info("Application shutdown complete")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass  # Handled by signal handlers
