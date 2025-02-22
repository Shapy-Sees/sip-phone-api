# src/sip_phone/utils/config.py
"""
Configuration management for SIP Phone API.
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
class LoggingConfig:
    """Logging configuration parameters"""
    level: str
    format: str
    handlers: dict

@dataclass
class APIConfig:
    """API configuration parameters"""
    host: str
    port: int
    debug: bool
    cors_origins: list[str]
    request_timeout: int
    max_upload_size: str

@dataclass
class WebSocketConfig:
    """WebSocket configuration parameters"""
    ping_interval: int
    ping_timeout: int
    max_message_size: str
    compression: bool

@dataclass
class SIPConfig:
    """SIP configuration parameters"""
    server: str
    user_agent: str
    registration_timeout: int
    retry_count: int
    retry_delay: int

@dataclass
class AudioConfig:
    """Audio configuration parameters"""
    sample_rate: int
    channels: int
    buffer_size: int
    codec: str
    dtmf: dict

@dataclass
class HardwareConfig:
    """Hardware configuration parameters"""
    ht802: dict

@dataclass
class WebhookConfig:
    """Webhook configuration parameters"""
    retry: dict
    endpoints: list[dict]

@dataclass
class OperatorConfig:
    """Operator configuration parameters"""
    url: str
    api_key: str
    timeout: int
    max_retries: int
    connection_check_interval: int

@dataclass
class EventsConfig:
    """Event system configuration parameters"""
    queue_size: int
    worker_threads: int
    retry_policy: dict

@dataclass
class SecurityConfig:
    """Security configuration parameters"""
    api_key_header: str
    allowed_api_keys: list[str]
    rate_limit: dict
    ssl: dict

@dataclass
class DevelopmentConfig:
    """Development configuration parameters"""
    mock_hardware: bool
    debug_dtmf: bool
    debug_audio: bool
    profile_enabled: bool

class ConfigurationError(Exception):
    """Custom exception for configuration errors"""
    pass

class Config:
    """
    Central configuration management for SIP Phone API.
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
            self.logging = None
            self.api = None
            self.websocket = None
            self.sip = None
            self.audio = None
            self.hardware = None
            self.webhooks = None
            self.operator = None
            self.events = None
            self.security = None
            self.development = None
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
            logger.debug(f"Logging config: {vars(self.logging)}")
            logger.debug(f"API config: {vars(self.api)}")
            logger.debug(f"WebSocket config: {vars(self.websocket)}")
            logger.debug(f"SIP config: {vars(self.sip)}")
            logger.debug(f"Audio config: {vars(self.audio)}")
            logger.debug(f"Hardware config: {vars(self.hardware)}")
            logger.debug(f"Webhooks config: {vars(self.webhooks)}")
            logger.debug(f"Operator config: {vars(self.operator)}")
            logger.debug(f"Events config: {vars(self.events)}")
            logger.debug(f"Security config: {vars(self.security)}")
            logger.debug(f"Development config: {vars(self.development)}")
            
        except Exception as e:
            logger.error(f"Failed to load configuration: {str(e)}", exc_info=True)
            raise ConfigurationError(f"Configuration loading failed: {str(e)}") from e

    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides to configuration"""
        env_mapping = {
            "API_HOST": ("api", "host"),
            "API_PORT": ("api", "port", int),
            "LOG_LEVEL": ("logging", "level"),
            "SIP_SERVER": ("sip", "server"),
            "HT802_HOST": ("hardware", "ht802", "host"),
            "HT802_PASSWORD": ("hardware", "ht802", "password"),
            "OPERATOR_URL": ("operator", "url"),
            "OPERATOR_API_KEY": ("operator", "api_key"),
            "DTMF_WEBHOOK_URL": ("webhooks", "endpoints", 0, "url"),
            "STATE_WEBHOOK_URL": ("webhooks", "endpoints", 1, "url"),
            "SYSTEM_WEBHOOK_URL": ("webhooks", "endpoints", 2, "url")
        }

        for env_var, config_path in env_mapping.items():
            if env_var in os.environ:
                value = os.environ[env_var]
                current_dict = self._raw_config
                
                # Navigate to the correct nested dictionary
                for i, key in enumerate(config_path[:-1]):
                    if isinstance(key, int):  # Handle list indices
                        while len(current_dict) <= key:
                            current_dict.append({})
                        current_dict = current_dict[key]
                    else:  # Handle dictionary keys
                        if key not in current_dict:
                            current_dict[key] = {}
                        current_dict = current_dict[key]
                
                # Set the final value
                final_key = config_path[-1]
                
                # Apply type conversion if specified
                if len(config_path) > 2 and not isinstance(config_path[-2], int):
                    try:
                        value = config_path[2](value)
                    except ValueError as e:
                        raise ConfigurationError(
                            f"Invalid environment variable {env_var}: {str(e)}"
                        )
                
                current_dict[final_key] = value
                logger.debug(f"Applied environment override: {env_var}={value}")

    def _validate_and_create_configs(self) -> None:
        """Validate configuration and create typed configuration objects"""
        try:
            # Logging configuration
            self.logging = LoggingConfig(
                level=self._get_config_value("logging", "level", str, "INFO"),
                format=self._get_config_value("logging", "format", str),
                handlers=self._get_config_value("logging", "handlers", dict)
            )

            # API configuration
            self.api = APIConfig(
                host=self._get_config_value("api", "host", str, "0.0.0.0"),
                port=self._get_config_value("api", "port", int, 8000),
                debug=self._get_config_value("api", "debug", bool, False),
                cors_origins=self._get_config_value("api", "cors_origins", list),
                request_timeout=self._get_config_value("api", "request_timeout", int, 30),
                max_upload_size=self._get_config_value("api", "max_upload_size", str, "10MB")
            )

            # WebSocket configuration
            self.websocket = WebSocketConfig(
                ping_interval=self._get_config_value("websocket", "ping_interval", int, 30),
                ping_timeout=self._get_config_value("websocket", "ping_timeout", int, 10),
                max_message_size=self._get_config_value("websocket", "max_message_size", str),
                compression=self._get_config_value("websocket", "compression", bool, True)
            )

            # SIP configuration
            self.sip = SIPConfig(
                server=self._get_config_value("sip", "server", str),
                user_agent=self._get_config_value("sip", "user_agent", str),
                registration_timeout=self._get_config_value("sip", "registration_timeout", int),
                retry_count=self._get_config_value("sip", "retry_count", int),
                retry_delay=self._get_config_value("sip", "retry_delay", int)
            )

            # Audio configuration
            self.audio = AudioConfig(
                sample_rate=self._get_config_value("audio", "sample_rate", int),
                channels=self._get_config_value("audio", "channels", int),
                buffer_size=self._get_config_value("audio", "buffer_size", int),
                codec=self._get_config_value("audio", "codec", str),
                dtmf=self._get_config_value("audio", "dtmf", dict)
            )

            # Hardware configuration
            self.hardware = HardwareConfig(
                ht802=self._get_config_value("hardware", "ht802", dict)
            )

            # Webhook configuration
            self.webhooks = WebhookConfig(
                retry=self._get_config_value("webhooks", "retry", dict),
                endpoints=self._get_config_value("webhooks", "endpoints", list)
            )

            # Operator configuration
            self.operator = OperatorConfig(
                url=self._get_config_value("operator", "url", str),
                api_key=self._get_config_value("operator", "api_key", str),
                timeout=self._get_config_value("operator", "timeout", int),
                max_retries=self._get_config_value("operator", "max_retries", int),
                connection_check_interval=self._get_config_value("operator", "connection_check_interval", int)
            )

            # Events configuration
            self.events = EventsConfig(
                queue_size=self._get_config_value("events", "queue_size", int),
                worker_threads=self._get_config_value("events", "worker_threads", int),
                retry_policy=self._get_config_value("events", "retry_policy", dict)
            )

            # Security configuration
            self.security = SecurityConfig(
                api_key_header=self._get_config_value("security", "api_key_header", str),
                allowed_api_keys=self._get_config_value("security", "allowed_api_keys", list),
                rate_limit=self._get_config_value("security", "rate_limit", dict),
                ssl=self._get_config_value("security", "ssl", dict)
            )

            # Development configuration
            self.development = DevelopmentConfig(
                mock_hardware=self._get_config_value("development", "mock_hardware", bool, False),
                debug_dtmf=self._get_config_value("development", "debug_dtmf", bool, False),
                debug_audio=self._get_config_value("development", "debug_audio", bool, False),
                profile_enabled=self._get_config_value("development", "profile_enabled", bool, False)
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
