"""Configuration management for channels-rpc.

This module provides configuration classes that integrate with Django settings,
allowing runtime configuration of limits, logging, and other parameters.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class RpcLimits:
    """Configuration for RPC request size limits.

    These limits protect against DoS attacks by restricting the size and
    complexity of incoming JSON-RPC requests.

    Attributes
    ----------
    max_message_size : int
        Maximum size in bytes for incoming messages (default: 10MB).
    max_array_length : int
        Maximum number of items in JSON arrays (default: 10,000).
    max_string_length : int
        Maximum length of JSON strings (default: 1MB).
    max_nesting_depth : int
        Maximum nesting depth of JSON structures (default: 20).
    max_method_name_length : int
        Maximum length of RPC method names (default: 256).

    Examples
    --------
    Create custom limits for high-volume environments::

        limits = RpcLimits(
            max_message_size=50 * 1024 * 1024,  # 50MB
            max_array_length=50000,
        )
    """

    max_message_size: int = 10 * 1024 * 1024  # 10MB
    max_array_length: int = 10000
    max_string_length: int = 1024 * 1024  # 1MB
    max_nesting_depth: int = 20
    max_method_name_length: int = 256

    @classmethod
    def from_settings(cls) -> RpcLimits:
        """Load limits from Django settings.

        Reads configuration from Django settings under the CHANNELS_RPC key.
        Falls back to default values if settings are not configured.

        Returns
        -------
        RpcLimits
            Limits instance with values from settings or defaults.

        Examples
        --------
        In Django settings.py::

            CHANNELS_RPC = {
                'MAX_MESSAGE_SIZE': 20 * 1024 * 1024,  # 20MB
                'MAX_ARRAY_LENGTH': 50000,
            }

        Then in code::

            limits = RpcLimits.from_settings()
            print(limits.max_message_size)  # 20971520
        """
        try:
            from django.conf import settings

            config = getattr(settings, "CHANNELS_RPC", {})

            return cls(
                max_message_size=config.get("MAX_MESSAGE_SIZE", cls.max_message_size),
                max_array_length=config.get("MAX_ARRAY_LENGTH", cls.max_array_length),
                max_string_length=config.get(
                    "MAX_STRING_LENGTH", cls.max_string_length
                ),
                max_nesting_depth=config.get(
                    "MAX_NESTING_DEPTH", cls.max_nesting_depth
                ),
                max_method_name_length=config.get(
                    "MAX_METHOD_NAME_LENGTH", cls.max_method_name_length
                ),
            )
        except ImportError:
            # Django not available, use defaults
            return cls()


@dataclass
class RpcConfig:
    """Main configuration for channels-rpc.

    Attributes
    ----------
    limits : RpcLimits
        Size and complexity limits for requests.
    log_rpc_params : bool
        Whether to log RPC method parameters (may contain PII).
    sanitize_errors : bool
        Whether to sanitize error messages in responses.

    Examples
    --------
    Get configuration from Django settings::

        config = RpcConfig.from_settings()
        if config.log_rpc_params:
            logger.debug("RPC params: %s", params)
    """

    limits: RpcLimits
    log_rpc_params: bool = False
    sanitize_errors: bool = True

    @classmethod
    def from_settings(cls) -> RpcConfig:
        """Load complete configuration from Django settings.

        Returns
        -------
        RpcConfig
            Configuration instance with values from settings or defaults.

        Examples
        --------
        In Django settings.py::

            CHANNELS_RPC = {
                'MAX_MESSAGE_SIZE': 20 * 1024 * 1024,
                'LOG_RPC_PARAMS': True,
                'SANITIZE_ERRORS': True,
            }
        """
        try:
            from django.conf import settings

            config_dict = getattr(settings, "CHANNELS_RPC", {})

            return cls(
                limits=RpcLimits.from_settings(),
                log_rpc_params=config_dict.get("LOG_RPC_PARAMS", False),
                sanitize_errors=config_dict.get("SANITIZE_ERRORS", True),
            )
        except ImportError:
            # Django not available, use defaults
            return cls(limits=RpcLimits())


# Global configuration instance
_config: RpcConfig | None = None


def get_config() -> RpcConfig:
    """Get the global RPC configuration instance.

    This function returns a cached configuration instance. On first call,
    it loads configuration from Django settings. Subsequent calls return
    the cached instance.

    Returns
    -------
    RpcConfig
        The global configuration instance.

    Notes
    -----
    The configuration is loaded once at startup. Changes to Django settings
    after the first call will not be reflected unless the application is
    restarted.

    Examples
    --------
    Get current configuration::

        from channels_rpc.config import get_config

        config = get_config()
        if config.sanitize_errors:
            # Hide sensitive error details
            ...
    """
    global _config
    if _config is None:
        _config = RpcConfig.from_settings()
    return _config


def reset_config() -> None:
    """Reset the global configuration cache.

    This function is primarily useful for testing, where you may want
    to reload configuration between tests.

    Examples
    --------
    In test teardown::

        def tearDown(self):
            from channels_rpc.config import reset_config
            reset_config()
    """
    global _config
    _config = None
