"""Request size limits for security."""

from typing import Any

# Maximum sizes to prevent DoS attacks
MAX_MESSAGE_SIZE: int = 10 * 1024 * 1024  # 10MB
MAX_ARRAY_LENGTH: int = 10000  # Maximum items in params array
MAX_STRING_LENGTH: int = 1024 * 1024  # 1MB per string
MAX_NESTING_DEPTH: int = 20  # Maximum depth of nested dicts/lists
MAX_METHOD_NAME_LENGTH: int = 256  # Maximum method name length


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
    from channels_rpc.exceptions import RequestTooLargeError  # noqa: PLC0415

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
    from channels_rpc.exceptions import RequestTooLargeError  # noqa: PLC0415

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
