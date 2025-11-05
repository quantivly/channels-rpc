"""Request size limits for security.

This module provides size limits that protect against DoS attacks. Limits can
be configured via Django settings or use sensible defaults.

Examples
--------
Configure limits in Django settings.py::

    CHANNELS_RPC = {
        'MAX_MESSAGE_SIZE': 20 * 1024 * 1024,  # 20MB
        'MAX_ARRAY_LENGTH': 50000,
    }

Or use the config API directly::

    from channels_rpc.config import RpcLimits

    limits = RpcLimits.from_settings()
    print(limits.max_message_size)

Notes
-----
For backward compatibility, this module still exports top-level constants.
However, these are loaded from Django settings if available, falling back
to defaults if not.

.. versionchanged:: 1.0.0
   Limits are now configurable via Django settings under CHANNELS_RPC key.
"""

from __future__ import annotations

from typing import Any

from channels_rpc.config import get_config
from channels_rpc.exceptions import RequestTooLargeError

# Lazy-load configuration to avoid requiring Django settings at import time
# This allows the module to be imported in test environments before Django is configured
_config = None


def _get_config():
    """Lazy-load configuration."""
    global _config  # noqa: PLW0603
    if _config is None:
        _config = get_config()
    return _config


# Removed mutable module constants - use _get_config().limits directly
# This prevents the anti-pattern of reassigning "constants" at runtime


def check_size_limits(data: dict, rpc_id: str | int | None = None) -> None:
    """Check if request data exceeds size limits.

    Parameters
    ----------
    data : dict
        The JSON-RPC request data.
    rpc_id : str | int | None, optional
        Request ID for error reporting.

    Raises
    ------
    RequestTooLargeError
        If any size limit is exceeded.
    """
    # Get limits from config (lazy-loaded)
    config = _get_config()
    limits = config.limits

    # Check method name length
    if "method" in data:
        method = data["method"]
        if isinstance(method, str) and len(method) > limits.max_method_name_length:
            raise RequestTooLargeError(
                rpc_id, "method_name_length", limits.max_method_name_length
            )

    # Check params
    if "params" in data:
        params = data["params"]
        _check_value_limits(params, rpc_id, limits, depth=0)


def _check_value_limits(
    value: Any, rpc_id: str | int | None, limits, depth: int
) -> None:
    """Recursively check value size limits.

    Parameters
    ----------
    value : Any
        The value to check.
    rpc_id : str | int | None
        Request ID for error reporting.
    limits : RpcLimits
        The limits configuration object.
    depth : int
        Current nesting depth.

    Raises
    ------
    RequestTooLargeError
        If any size limit is exceeded.
    """
    # Check nesting depth
    if depth > limits.max_nesting_depth:
        raise RequestTooLargeError(rpc_id, "nesting_depth", limits.max_nesting_depth)

    # Check string length
    if isinstance(value, str) and len(value) > limits.max_string_length:
        raise RequestTooLargeError(rpc_id, "string_length", limits.max_string_length)

    # Check array length and recurse
    elif isinstance(value, list):
        if len(value) > limits.max_array_length:
            raise RequestTooLargeError(rpc_id, "array_length", limits.max_array_length)
        for item in value:
            _check_value_limits(item, rpc_id, limits, depth + 1)

    # Recurse into dicts
    elif isinstance(value, dict):
        for k, v in value.items():
            _check_value_limits(k, rpc_id, limits, depth + 1)
            _check_value_limits(v, rpc_id, limits, depth + 1)
