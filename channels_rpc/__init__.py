"""Django Channels JSON-RPC 2.0 implementation.

This package provides WebSocket consumers for implementing JSON-RPC 2.0 servers
using Django Channels.

Public API
----------
Consumers:
    - AsyncJsonRpcWebsocketConsumer: Async WebSocket JSON-RPC consumer

Context:
    - RpcContext: Execution context for RPC methods

Middleware:
    - RpcMiddleware: Protocol for middleware components
    - LoggingMiddleware: Example middleware for logging RPC calls

Exceptions:
    - JsonRpcError: Base JSON-RPC error exception
    - JsonRpcErrorCode: Enum of JSON-RPC 2.0 error codes
    - RequestTooLargeError: Exception for oversized requests

Error Codes:
    Use the JsonRpcErrorCode enum to access error codes:
    - JsonRpcErrorCode.PARSE_ERROR
    - JsonRpcErrorCode.INVALID_REQUEST
    - JsonRpcErrorCode.METHOD_NOT_FOUND
    - JsonRpcErrorCode.INVALID_PARAMS
    - JsonRpcErrorCode.INTERNAL_ERROR
    - JsonRpcErrorCode.GENERIC_APPLICATION_ERROR
    - JsonRpcErrorCode.PARSE_RESULT_ERROR
    - JsonRpcErrorCode.REQUEST_TOO_LARGE

Configuration:
    Configure limits and behavior via Django settings::

        CHANNELS_RPC = {
            'MAX_MESSAGE_SIZE': 20 * 1024 * 1024,
            'MAX_ARRAY_LENGTH': 50000,
            'LOG_RPC_PARAMS': False,
        }

    Or access limits from config programmatically::

        from channels_rpc.config import get_config
        config = get_config()
        print(config.limits.max_message_size)

Notes
-----
.. versionchanged:: 1.0.0
   Added Django settings integration and AppConfig support.
"""

from channels_rpc.async_json_rpc_websocket_consumer import (
    AsyncJsonRpcWebsocketConsumer,
)
from channels_rpc.context import RpcContext
from channels_rpc.decorators import permission_required
from channels_rpc.exceptions import (
    JsonRpcError,
    JsonRpcErrorCode,
    RequestTooLargeError,
)
from channels_rpc.limits import check_size_limits
from channels_rpc.middleware import LoggingMiddleware, RpcMiddleware

__all__ = [
    "AsyncJsonRpcWebsocketConsumer",
    "JsonRpcError",
    "JsonRpcErrorCode",
    "LoggingMiddleware",
    "RequestTooLargeError",
    "RpcContext",
    "RpcMiddleware",
    "check_size_limits",
    "permission_required",
]
