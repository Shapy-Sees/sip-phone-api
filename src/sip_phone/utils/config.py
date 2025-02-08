# src/sip_phone/utils/config.py
"""
Configuration management for DAHDI Phone API.
Handles loading and validating configuration from YAML files and environment variables.
Provides type-safe access to configuration values with comprehensive error checking.
"""

import os
import yaml
import logging
from typing import Any, Dict, Optional, Union
from dataclasses import dataclass
from pathlib import Path

# Configure module logger
logger = logging.getLogger(__name__)

@dataclass
class ServerConfig:
    """Server configuration parameters"""
    host: str
    rest_port: int
    websocket_port: int
    workers: int

@dataclass
class DAHDIConfig:
    """DAHDI hardware configuration parameters"""
    device: str
    control: str
    channel: int
    sample_rate: int
    channels: int
    bit_depth: int
    buffer_size: int

@dataclass
class LogConfig:
    """Logging configuration parameters"""
    level: str
    format: str
    output: str
    rotation: str
    retention: str

@dataclass
class APIConfig:
    """API behavior configuration parameters"""
    rate_limit: int
    timeout: int
    max_connections: int

@dataclass
class WebSocketConfig:
    """WebSocket configuration parameters"""
    ping_interval: int
    ping_timeout: int
    max_message_size: int

@dataclass
class SecurityConfig:
    """Security configuration parameters"""
    allowed_origins: list[str]
    api_tokens: list[str]

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class Config:
    """
    Central configuration management for DAHDI Phone API.
    Handles loading, validation, and access to configuration values.
    """
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not self._initialized:
            self.server = None
            self.dahdi = None
            self.logging = None
            self.api = None
            self.websocket = None
            self.security = None
            self._config_path = None
            self._raw_config = {}
            self._initialized = True
            logger.debug("Configuration manager initialized")

    def load(self, config_path: Union[str, Path]) -> None:
        """
        Load configuration from YAML file with environment variable overrides.
        
        Args:
            config_path: Path to YAML configuration file
            
        Raises:
            ConfigurationError: If configuration loading or validation fails
        """
        try:
            logger.debug(f"Attempting to load configuration from {config_path}")
            self._config_path = Path(config_path)
            
            if not self._config_path.exists():
                raise ConfigurationError(f"Configuration file not found: {config_path}")

            # Load the specified configuration file
            with open(self._config_path) as f:
                config_data = yaml.safe_load(f) or {}
                
            # If this is default.yml, set it as base config
            if self._config_path.name == "default.yml":
                self._raw_config = config_data
                logger.debug(f"Loaded default configuration from {self._config_path}")
                logger.debug(f"Default config contents: {self._raw_config}")
            # Otherwise merge with existing config
            else:
                self._merge_configs(config_data)
                logger.debug(f"Merged custom configuration from {self._config_path}")
                logger.debug(f"Final merged config contents: {self._raw_config}")

            # Apply environment variable overrides
            self._apply_env_overrides()
            
            # Validate and create configuration objects
            self._validate_and_create_configs()
            
            logger.info(f"Configuration loaded successfully from {self._config_path}")
            logger.debug("Final configuration after environment overrides and validation:")
            logger.debug(f"Server config: {vars(self.server)}")
            logger.debug(f"DAHDI config: {vars(self.dahdi)}")
            logger.debug(f"Logging config: {vars(self.logging)}")
            logger.debug(f"API config: {vars(self.api)}")
            logger.debug(f"WebSocket config: {vars(self.websocket)}")
            logger.debug(f"Security config: {vars(self.security)}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}", exc_info=True)
            raise ConfigurationError(f"Configuration loading failed: {str(e)}") from e

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration"""
        env_mapping = {
            "DAHDI_API_HOST": ("server", "host"),
            "DAHDI_API_REST_PORT": ("server", "rest_port", int),
            "DAHDI_API_WS_PORT": ("server", "websocket_port", int),
            "DAHDI_DEVICE": ("dahdi", "device"),
            "DAHDI_CHANNEL": ("dahdi", "channel", int),
            "LOG_LEVEL": ("logging", "level"),
            "LOG_OUTPUT": ("logging", "output"),
            "API_TIMEOUT": ("api", "timeout", int),
            "API_RATE_LIMIT": ("api", "rate_limit", int),
        }

        for env_var, config_path in env_mapping.items():
            if env_var in os.environ:
                section, key = config_path[0], config_path[1]
                value = os.environ[env_var]
                
                # Apply type conversion if specified
                if len(config_path) > 2:
                    try:
                        value = config_path[2](value)
                    except ValueError as e:
                        raise ConfigurationError(
                            f"Invalid environment variable {env_var}: {str(e)}"
                        )

                # Ensure section exists
                if section not in self._raw_config:
                    self._raw_config[section] = {}
                    
                self._raw_config[section][key] = value
                logger.debug(f"Applied environment override: {env_var}={value}")

    def _validate_and_create_configs(self) -> None:
        """Validate configuration and create typed configuration objects"""
        try:
            # Server configuration
            self.server = ServerConfig(
                host=self._get_config_value("server", "host", str, "0.0.0.0"),
                rest_port=self._get_config_value("server", "rest_port", int, 8000),
                websocket_port=self._get_config_value("server", "websocket_port", int, 8001),
                workers=self._get_config_value("server", "workers", int, 4)
            )

            # DAHDI configuration
            audio_config = self._raw_config.get("dahdi", {}).get("audio", {})
            self.dahdi = DAHDIConfig(
                device=self._get_config_value("dahdi", "device", str),
                control=self._get_config_value("dahdi", "control", str),
                channel=self._get_config_value("dahdi", "channel", int),
                sample_rate=self._get_config_value("audio", "sample_rate", int, 8000, audio_config),
                channels=self._get_config_value("audio", "channels", int, 1, audio_config),
                bit_depth=self._get_config_value("audio", "bit_depth", int, 16, audio_config),
                buffer_size=self._get_config_value("dahdi", "buffer_size", int, 320)
            )

            # Logging configuration
            self.logging = LogConfig(
                level=self._get_config_value("logging", "level", str, "INFO"),
                format=self._get_config_value("logging", "format", str, "json"),
                output=self._get_config_value("logging", "output", str),
                rotation=self._get_config_value("logging", "rotation", str, "1 day"),
                retention=self._get_config_value("logging", "retention", str, "30 days")
            )

            # API configuration
            self.api = APIConfig(
                rate_limit=self._get_config_value("api", "rate_limit", int, 100),
                timeout=self._get_config_value("api", "timeout", int, 30),
                max_connections=self._get_config_value("api", "max_connections", int, 1000)
            )

            # WebSocket configuration
            self.websocket = WebSocketConfig(
                ping_interval=self._get_config_value("websocket", "ping_interval", int, 30),
                ping_timeout=self._get_config_value("websocket", "ping_timeout", int, 10),
                max_message_size=self._get_config_value("websocket", "max_message_size", int, 1048576)
            )

            # Security configuration
            self.security = SecurityConfig(
                allowed_origins=self._get_config_value("security", "allowed_origins", list, ["*"]),
                api_tokens=self._get_config_value("security", "api_tokens", list, [])
            )

            logger.debug("Configuration validation completed successfully")

        except Exception as e:
            logger.error("Configuration validation failed", exc_info=True)
            raise ConfigurationError(f"Configuration validation failed: {str(e)}") from e

    def _get_config_value(
        self,
        section: str,
        key: str,
        value_type: type,
        default: Any = None,
        config_dict: Optional[Dict] = None
    ) -> Any:
        """
        Get typed configuration value with validation.
        
        Args:
            section: Configuration section name
            key: Configuration key
            value_type: Expected value type
            default: Optional default value
            config_dict: Optional alternative configuration dictionary
            
        Returns:
            Typed configuration value
            
        Raises:
            ConfigurationError: If value is missing or invalid type
        """
        config = config_dict if config_dict is not None else self._raw_config.get(section, {})
        value = config.get(key)

        if value is None:
            if default is None:
                raise ConfigurationError(f"Required configuration missing: {section}.{key}")
            value = default
            logger.debug(f"Using default value for {section}.{key}: {default}")

        try:
            if value_type == list and isinstance(value, str):
                value = [value]
            elif not isinstance(value, value_type):
                value = value_type(value)
        except (ValueError, TypeError) as e:
            raise ConfigurationError(
                f"Invalid type for {section}.{key}: expected {value_type.__name__}, got {type(value).__name__}"
            ) from e

        return value

    def _merge_configs(self, custom_config: Dict[str, Any]) -> None:
        """Deep merge custom configuration with existing config"""
        def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> None:
            for key, value in override.items():
                if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                    deep_merge(base[key], value)
                else:
                    base[key] = value

        deep_merge(self._raw_config, custom_config)

    def reload(self) -> None:
        """Reload configuration from file"""
        logger.info("Reloading configuration")
        if self._config_path:
            self.load(self._config_path)
        else:
            raise ConfigurationError("No configuration path set, cannot reload")

# Example usage:
"""
# Get configuration instance
config = Config()

# Load configuration
config.load("/etc/dahdi_phone/config.yml")

# Access configuration values
rest_port = config.server.rest_port
log_level = config.logging.level

# Reload configuration if needed
config.reload()
"""
