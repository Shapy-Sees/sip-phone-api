# src/sip_phone/utils/logger.py
"""
Centralized logging configuration for the SIP Phone API.
Provides consistent, configurable logging across all modules with support for
different output formats, log levels, and destinations.
"""

import logging
import logging.handlers
import json
import os
import sys
from datetime import datetime
from functools import wraps
from typing import Optional, Callable, Any, Dict
import structlog
from pathlib import Path

# Default logging format for traditional logging
DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"

# Logging levels dictionary for configuration
LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL
}

class LoggerConfig:
    """Configuration class for logger settings"""
    def __init__(
        self,
        level: str = "INFO",
        format: str = "json",
        output_file: Optional[str] = None,
        max_bytes: int = 10_485_760,  # 10MB
        backup_count: int = 5,
        include_timestamp: bool = True,
        include_caller_info: bool = True
    ):
        self.level = LOG_LEVELS.get(level.upper(), logging.INFO)
        self.format = format.lower()
        self.output_file = output_file
        self.max_bytes = max_bytes
        self.backup_count = backup_count
        self.include_timestamp = include_timestamp
        self.include_caller_info = include_caller_info

class SIPLogger:
    """
    Central logging facility for SIP Phone API.
    Provides structured logging with configurable outputs and formats.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self._logger = None
            self._config = None
            self._initialized = True

    def configure(self, config: LoggerConfig) -> None:
        """
        Configure the logger with the provided settings.
        
        Args:
            config: LoggerConfig instance with desired settings
        """
        self._config = config
        
        # Create log directory if it doesn't exist
        if config.output_file:
            os.makedirs(os.path.dirname(config.output_file), exist_ok=True)

        # Set up structlog processors
        processors = [
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.stdlib.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
        ]

        if config.format == "json":
            processors.append(structlog.processors.JSONRenderer())
        else:
            processors.append(structlog.dev.ConsoleRenderer())

        # Configure structlog
        structlog.configure(
            processors=processors,
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        # Set up root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(config.level)
        
        # Clear existing handlers
        root_logger.handlers = []

        # Create handlers
        handlers = []
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(config.level)
        handlers.append(console_handler)

        # File handler if output file specified
        if config.output_file:
            file_handler = logging.handlers.RotatingFileHandler(
                config.output_file,
                maxBytes=config.max_bytes,
                backupCount=config.backup_count
            )
            file_handler.setLevel(config.level)
            handlers.append(file_handler)

        # Create JSON formatter class
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                return self._json_formatter(record)
                
            def _json_formatter(self, record):
                """Custom JSON formatter for log records"""
                log_data = {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": record.levelname,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno
                }
                
                if hasattr(record, "stack_info") and record.stack_info:
                    log_data["stack_info"] = record.stack_info
                    
                if record.exc_info:
                    log_data["exc_info"] = self._format_exception(record.exc_info)
                    
                return json.dumps(log_data)
                
            def _format_exception(self, exc_info):
                """Format exception information for JSON logging"""
                if not exc_info:
                    return None
                    
                return {
                    "type": str(exc_info[0].__name__),
                    "message": str(exc_info[1]),
                    "traceback": self._format_traceback(exc_info[2])
                }

            def _format_traceback(self, tb):
                """Format traceback for JSON logging"""
                import traceback
                return [str(line) for line in traceback.extract_tb(tb).format()]

        # Set formatter based on format choice
        if config.format == "json":
            formatter = JSONFormatter()
        else:
            formatter = logging.Formatter(DEFAULT_LOG_FORMAT)

        # Apply formatter to all handlers
        for handler in handlers:
            handler.setFormatter(formatter)
            root_logger.addHandler(handler)

        self._logger = structlog.get_logger()
        self._logger.info("Logger configured", 
                         level=config.level,
                         format=config.format,
                         output_file=config.output_file)

    def get_logger(self, name: str = None) -> structlog.BoundLogger:
        """
        Get a logger instance with the given name.
        
        Args:
            name: Optional name for the logger (defaults to module name)
            
        Returns:
            Configured logger instance
        """
        if not self._logger:
            raise RuntimeError("Logger not configured. Call configure() first.")
        
        logger = structlog.get_logger(name)
        return logger

def log_function_call(level: str = "DEBUG") -> Callable:
    """
    Decorator to log function calls with arguments and return values.
    
    Args:
        level: Logging level for the function calls
        
    Returns:
        Decorator function
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            logger = SIPLogger().get_logger(func.__module__)
            log_level = getattr(logging, level.upper())
            
            # Log function entry
            logger.log(log_level, 
                      "Function call",
                      function=func.__name__,
                      args=str(args),
                      kwargs=str(kwargs))
            
            try:
                result = func(*args, **kwargs)
                # Log successful return
                logger.log(log_level,
                          "Function return",
                          function=func.__name__,
                          result=str(result))
                return result
            except Exception as e:
                # Log exception
                logger.error("Function exception",
                           function=func.__name__,
                           error=str(e),
                           exc_info=True)
                raise
                
        return wrapper
    return decorator

# Example usage:
"""
# Configure the logger
logger_config = LoggerConfig(
    level="DEBUG",
    format="json",
    output_file="/var/log/sip_phone/api.log"
)
logger = SIPLogger()
logger.configure(logger_config)

# Get a logger instance
log = logger.get_logger(__name__)

# Use the logger
log.info("Application started")
log.debug("Debug message", extra_field="value")
log.error("Error occurred", exc_info=True)

# Use the decorator
@log_function_call(level="DEBUG")
def example_function(arg1, arg2):
    return arg1 + arg2
"""
