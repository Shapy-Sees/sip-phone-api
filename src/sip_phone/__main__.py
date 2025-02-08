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
from .websocket.server import WebSocketServer

async def shutdown(sip_server: Optional[SIPServer] = None,
                  api_server: Optional[APIServer] = None,
                  ws_server: Optional[WebSocketServer] = None) -> None:
    """
    Gracefully shut down all services.
    
    Args:
        sip_server: SIP server instance
        api_server: API server instance
        ws_server: WebSocket server instance
    """
    logger = SIPLogger().get_logger(__name__)
    logger.info("Initiating graceful shutdown")
    
    if ws_server:
        logger.debug("Stopping WebSocket server")
        await ws_server.stop()
        
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
        
        # Initialize servers
        sip_server = SIPServer()
        api_server = APIServer(sip_server)
        ws_server = WebSocketServer(sip_server)
        
        # Setup signal handlers for graceful shutdown
        loop = asyncio.get_running_loop()
        signals = (signal.SIGHUP, signal.SIGTERM, signal.SIGINT)
        for s in signals:
            loop.add_signal_handler(
                s,
                lambda s=s: asyncio.create_task(
                    shutdown(sip_server, api_server, ws_server)
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
        
        # Start WebSocket server
        log.debug("Starting WebSocket server")
        await ws_server.start()
        
        log.info("All services started successfully",
                 sip_port=config.server.sip_port,
                 api_port=config.server.rest_port,
                 ws_port=config.server.websocket_port)
        
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