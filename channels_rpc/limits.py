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

from typing import Any

from channels_rpc.config import get_config

# Load configuration early
_config = get_config()

# Export as module-level constants for backward compatibility
# These will use values from Django settings if configured
MAX_MESSAGE_SIZE: int = _config.limits.max_message_size
MAX_ARRAY_LENGTH: int = _config.limits.max_array_length
MAX_STRING_LENGTH: int = _config.limits.max_string_length
MAX_NESTING_DEPTH: int = _config.limits.max_nesting_depth
MAX_METHOD_NAME_LENGTH: int = _config.limits.max_method_name_length


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
    from channels_rpc.exceptions import RequestTooLargeError

    # Check method name length
    if "method" in data:
        method = data["method"]
        if isinstance(method, str) and len(method) > MAX_METHOD_NAME_LENGTH:
            raise RequestTooLargeError(
                rpc_id, "method_name_length", MAX_METHOD_NAME_LENGTH
            )

    # Check params
    if "params" in data:
        params = data["params"]
        _check_value_limits(params, rpc_id, depth=0)


def _check_value_limits(value: Any, rpc_id: str | int | None, depth: int) -> None:
    """Recursively check value size limits.

    Parameters
    ----------
    value : Any
        The value to check.
    rpc_id : str | int | None
        Request ID for error reporting.
    depth : int
        Current nesting depth.

    Raises
    ------
    RequestTooLargeError
        If any size limit is exceeded.
    """
    from channels_rpc.exceptions import RequestTooLargeError

    # Check nesting depth
    if depth > MAX_NESTING_DEPTH:
        raise RequestTooLargeError(rpc_id, "nesting_depth", MAX_NESTING_DEPTH)

    # Check string length
    if isinstance(value, str) and len(value) > MAX_STRING_LENGTH:
        raise RequestTooLargeError(rpc_id, "string_length", MAX_STRING_LENGTH)

    # Check array length and recurse
    elif isinstance(value, list):
        if len(value) > MAX_ARRAY_LENGTH:
            raise RequestTooLargeError(rpc_id, "array_length", MAX_ARRAY_LENGTH)
        for item in value:
            _check_value_limits(item, rpc_id, depth + 1)

    # Recurse into dicts
    elif isinstance(value, dict):
        for k, v in value.items():
            _check_value_limits(k, rpc_id, depth + 1)
            _check_value_limits(v, rpc_id, depth + 1)
