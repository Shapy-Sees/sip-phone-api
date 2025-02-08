# src/sip_phone/utils/errors.py
"""
Custom exception classes for the SIP Phone API.
Provides specific error types for different failure scenarios.
"""

class SipPhoneError(Exception):
    """Base exception class for all SIP Phone API errors."""
    pass

class ConfigurationError(SipPhoneError):
    """Raised when there is an error in the configuration."""
    pass

class WebhookDeliveryError(SipPhoneError):
    """Raised when webhook delivery fails."""
    pass

class OperatorConnectionError(SipPhoneError):
    """Raised when there are issues connecting to the operator server."""
    pass

class HardwareError(SipPhoneError):
    """Raised when there are issues with hardware devices."""
    pass

class SipProtocolError(SipPhoneError):
    """Raised when there are SIP protocol related errors."""
    pass

class DtmfError(SipPhoneError):
    """Raised when there are issues with DTMF processing."""
    pass

class StateError(SipPhoneError):
    """Raised when there are invalid state transitions."""
    pass

class AudioError(SipPhoneError):
    """Raised when there are issues with audio processing."""
    pass
