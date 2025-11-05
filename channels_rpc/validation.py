"""Shared validation logic for RPC base classes.

This module contains validation functions used by both sync (RpcBase) and async
(AsyncRpcBase) consumers to avoid code duplication.
"""

from __future__ import annotations

import logging
from typing import Any

from channels_rpc import logs
from channels_rpc.exceptions import (
    RPC_ERRORS,
    JsonRpcErrorCode,
    generate_error_response,
)

logger = logging.getLogger("channels_rpc")


def validate_rpc_data(data: Any) -> tuple[dict[str, Any] | None, bool]:
    """Validate RPC data and determine if it's a response.

    Performs common validation checks that apply to both sync and async consumers:
    - Checks for empty data
    - Validates that data is a dict
    - Detects if data is a response (has "result" or "error")

    Parameters
    ----------
    data : Any
        The data to validate (should be dict).

    Returns
    -------
    tuple[dict[str, Any] | None, bool]
        Returns (error_response, True) if validation fails or data is a response.
        Returns (None, False) if data is a valid request that should be processed.

    Examples
    --------
    >>> error, is_response = validate_rpc_data({})
    >>> if error:
    ...     return error
    >>> error, is_response = validate_rpc_data({"jsonrpc": "2.0", "method": "test"})
    >>> error  # None - valid request
    >>> is_response  # False - not a response
    """
    # Check for empty data
    if not data:
        logger.warning(logs.EMPTY_CALL)
        message = RPC_ERRORS[JsonRpcErrorCode.INVALID_REQUEST]
        return (
            generate_error_response(
                rpc_id=None, code=JsonRpcErrorCode.INVALID_REQUEST, message=message
            ),
            False,
        )

    # Check data type
    if not isinstance(data, dict):
        logger.warning("Invalid message type: %s", type(data).__name__)
        message = RPC_ERRORS[JsonRpcErrorCode.INVALID_REQUEST]
        return (
            generate_error_response(
                rpc_id=None, code=JsonRpcErrorCode.INVALID_REQUEST, message=message
            ),
            False,
        )

    # Detect if this is a response (not a request to process)
    if "result" in data or "error" in data:
        logger.debug("Received JSON-RPC 2.0 response: %s", data)
        return data, True

    # Data is valid, proceed with processing
    return None, False


def is_rpc_response(data: dict[str, Any]) -> bool:
    """Check if data is an RPC response (vs request).

    Parameters
    ----------
    data : dict[str, Any]
        Data to check.

    Returns
    -------
    bool
        True if data is a response, False if it's a request.

    Examples
    --------
    >>> is_rpc_response({"jsonrpc": "2.0", "result": 42, "id": 1})
    True
    >>> is_rpc_response({"jsonrpc": "2.0", "method": "test", "id": 1})
    False
    """
    return "result" in data or "error" in data
