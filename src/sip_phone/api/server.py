# src/sip_phone/api/server.py
"""
FastAPI server implementation for the SIP Phone API.
Provides REST API endpoints and WebSocket support for real-time communication.
Handles request routing, middleware configuration, and server lifecycle management.
"""

import asyncio
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from typing import Callable, Dict, List, Tuple, Optional

from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog
import uvicorn

from sip_phone.utils.logger import LoggerConfig, DAHDILogger as SIPLogger
from sip_phone.utils.config import load_config
from sip_phone.api.routes import router as api_router
from sip_phone.api.websocket.manager import init_connection_manager
from sip_phone.api.websocket.audio import init_audio_stream_manager

# Initialize structured logger
logger = SIPLogger().get_logger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifecycle manager for the FastAPI application.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info("Starting SIP Phone API server")
    config = load_config()
    app.state.startup_time = time.time()
    
    # Initialize subsystems
    try:
        # Initialize WebSocket managers
        app.state.connection_manager = init_connection_manager(config)
        app.state.audio_manager = init_audio_stream_manager(config)
        
        logger.info("All subsystems initialized successfully")
        yield
    except Exception as e:
        logger.error("Failed to initialize subsystems", error=str(e), exc_info=True)
        raise
    finally:
        # Shutdown sequence
        logger.info("Beginning shutdown sequence")
        try:
            # Stop audio processing
            if hasattr(app.state, 'audio_manager'):
                await app.state.audio_manager.audio_processor.stop()
            
            # Close all WebSocket connections
            if hasattr(app.state, 'connection_manager'):
                for ws in list(app.state.connection_manager.control_connections):
                    await app.state.connection_manager.disconnect(ws)
                for ws in list(app.state.connection_manager.event_connections):
                    await app.state.connection_manager.disconnect(ws)
            
            logger.info("Shutdown completed successfully")
        except Exception as e:
            logger.error("Error during shutdown", error=str(e), exc_info=True)

class SIPPhoneAPI:
    """
    Main API server class that configures and runs the FastAPI application.
    Handles middleware setup, route configuration, and server lifecycle.
    """
    
    def __init__(self):
        """Initialize the API server with default configuration."""
        self.config = load_config()
        self._configure_logging()
        self.app = self._create_application()
        
    def _configure_logging(self) -> None:
        """Configure logging based on application settings."""
        log_config = LoggerConfig(
            level=self.config.get("logging", {}).get("level", "INFO"),
            format=self.config.get("logging", {}).get("format", "json"),
            output_file=self.config.get("logging", {}).get("file", None)
        )
        SIPLogger().configure(log_config)
        
    def _create_application(self) -> FastAPI:
        """
        Create and configure the FastAPI application.
        Sets up middleware, exception handlers, and routes.
        """
        app = FastAPI(
            title="SIP Phone API",
            description="REST API for managing SIP phone functionality",
            version="1.0.0",
            lifespan=lifespan
        )
        
        # Configure CORS
        app.add_middleware(
            CORSMiddleware,
            allow_origins=self.config.get("cors", {}).get("origins", ["*"]),
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
        
        # Add request timing middleware
        @app.middleware("http")
        async def timing_middleware(request: Request, call_next: Callable) -> Response:
            """Track request timing information."""
            start_time = time.time()
            response = await call_next(request)
            process_time = (time.time() - start_time) * 1000  # Convert to milliseconds
            response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
            return response

        # Add enhanced logging middleware
        @app.middleware("http")
        async def logging_middleware(request: Request, call_next: Callable) -> Response:
            """Log incoming requests and outgoing responses with timing and details."""
            start_time = time.time()
            request_id = str(int(start_time * 1000))  # Simple request ID based on timestamp
            
            # Extract request details
            request_details = {
                "request_id": request_id,
                "method": request.method,
                "url": str(request.url),
                "client_ip": request.client.host if request.client else None,
                "headers": dict(request.headers),
                "query_params": dict(request.query_params),
                "path_params": dict(getattr(request.state, "path_params", {}))
            }
            
            # Log request
            logger.debug("Request received", **request_details)
            
            try:
                # Process request
                response = await call_next(request)
                process_time = (time.time() - start_time) * 1000
                
                # Log successful response
                logger.debug(
                    "Response sent",
                    request_id=request_id,
                    status_code=response.status_code,
                    process_time_ms=f"{process_time:.2f}",
                    content_type=response.headers.get("content-type"),
                    content_length=response.headers.get("content-length")
                )
                
                # Add timing and request ID headers
                response.headers["X-Request-ID"] = request_id
                response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
                
                return response
            except Exception as e:
                # Log error with full context
                process_time = (time.time() - start_time) * 1000
                logger.error(
                    "Request processing failed",
                    request_id=request_id,
                    error=str(e),
                    error_type=type(e).__name__,
                    process_time_ms=f"{process_time:.2f}",
                    **request_details,
                    exc_info=True
                )
                
                # Create error response with timing headers
                error_response = JSONResponse(
                    status_code=500,
                    content={"detail": "Internal server error"}
                )
                error_response.headers["X-Request-ID"] = request_id
                error_response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
                
                return error_response
        
        # Rate limiting configuration
        self.rate_limit_window = self.config.get("rate_limit", {}).get("window", 60)  # seconds
        self.rate_limit_max_requests = self.config.get("rate_limit", {}).get("max_requests", 100)
        self.rate_limits: Dict[str, List[float]] = defaultdict(list)

        # Add rate limiting middleware
        @app.middleware("http")
        async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
            """
            Rate limiting middleware based on client IP.
            Implements a sliding window rate limit.
            """
            client_ip = request.client.host if request.client else "unknown"
            now = time.time()
            
            # Clean up old requests
            self.rate_limits[client_ip] = [
                timestamp for timestamp in self.rate_limits[client_ip]
                if now - timestamp < self.rate_limit_window
            ]
            
            # Check rate limit
            if len(self.rate_limits[client_ip]) >= self.rate_limit_max_requests:
                logger.warning(
                    "Rate limit exceeded",
                    client_ip=client_ip,
                    request_count=len(self.rate_limits[client_ip])
                )
                raise HTTPException(
                    status_code=429,
                    detail="Too many requests. Please try again later."
                )
            
            # Add current request timestamp
            self.rate_limits[client_ip].append(now)
            
            return await call_next(request)
        
        # Register API routes
        app.include_router(api_router, prefix="/api/v1")
        
        # Health check endpoint
        @app.get("/health", tags=["System"])
        async def health_check():
            """Health check endpoint for monitoring."""
            return {"status": "healthy"}
            
        # Error handlers
        @app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            """Handle request validation errors."""
            logger.warning(
                "Validation error",
                errors=exc.errors(),
                body=await request.body(),
                method=request.method,
                url=str(request.url)
            )
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "detail": "Validation error",
                    "errors": exc.errors()
                }
            )

        @app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            """Handle HTTP exceptions."""
            logger.warning(
                "HTTP exception",
                status_code=exc.status_code,
                detail=exc.detail,
                method=request.method,
                url=str(request.url)
            )
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": exc.detail}
            )

        @app.exception_handler(Exception)
        async def generic_exception_handler(request: Request, exc: Exception):
            """Handle uncaught exceptions."""
            logger.error(
                "Unhandled exception",
                error=str(exc),
                method=request.method,
                url=str(request.url),
                exc_info=True
            )
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )

        # Add system info endpoint
        @app.get("/system/info", tags=["System"])
        async def system_info():
            """Get system information and status."""
            uptime = time.time() - app.state.startup_time
            return {
                "status": "healthy",
                "version": app.version,
                "uptime_seconds": int(uptime),
                "rate_limit": {
                    "window": self.rate_limit_window,
                    "max_requests": self.rate_limit_max_requests
                }
            }
        
        return app
    
    def run(self, host: str = "0.0.0.0", port: int = 8000) -> None:
        """
        Run the API server using uvicorn.
        
        Args:
            host: Host address to bind to
            port: Port number to listen on
        """
        logger.info(f"Starting server on {host}:{port}")
        uvicorn.run(
            self.app,
            host=host,
            port=port,
            log_level=self.config.get("logging", {}).get("level", "info").lower()
        )

# Example usage:
if __name__ == "__main__":
    api = SIPPhoneAPI()
    api.run()
