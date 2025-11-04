"""Django Channels JSON-RPC 2.0 implementation.

This package provides WebSocket consumers for implementing JSON-RPC 2.0 servers
using Django Channels.

Public API
----------
Consumers:
    - AsyncJsonRpcWebsocketConsumer: Async WebSocket JSON-RPC consumer
    - JsonRpcWebsocketConsumer: Sync WebSocket JSON-RPC consumer

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

Size Limits (for custom validation):
    - MAX_MESSAGE_SIZE, MAX_ARRAY_LENGTH, MAX_STRING_LENGTH
    - MAX_NESTING_DEPTH, MAX_METHOD_NAME_LENGTH

Configuration:
    Configure limits and behavior via Django settings::

        CHANNELS_RPC = {
            'MAX_MESSAGE_SIZE': 20 * 1024 * 1024,
            'MAX_ARRAY_LENGTH': 50000,
            'LOG_RPC_PARAMS': False,
        }

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
from channels_rpc.json_rpc_websocket_consumer import JsonRpcWebsocketConsumer
from channels_rpc.limits import (
    MAX_ARRAY_LENGTH,
    MAX_MESSAGE_SIZE,
    MAX_METHOD_NAME_LENGTH,
    MAX_NESTING_DEPTH,
    MAX_STRING_LENGTH,
    check_size_limits,
)
from channels_rpc.middleware import LoggingMiddleware, RpcMiddleware

__all__ = [
    "MAX_ARRAY_LENGTH",
    "MAX_MESSAGE_SIZE",
    "MAX_METHOD_NAME_LENGTH",
    "MAX_NESTING_DEPTH",
    "MAX_STRING_LENGTH",
    "AsyncJsonRpcWebsocketConsumer",
    "JsonRpcError",
    "JsonRpcErrorCode",
    "JsonRpcWebsocketConsumer",
    "LoggingMiddleware",
    "RequestTooLargeError",
    "RpcContext",
    "RpcMiddleware",
    "check_size_limits",
    "permission_required",
]
