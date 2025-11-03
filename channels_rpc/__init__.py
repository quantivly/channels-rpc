"""Django Channels JSON-RPC 2.0 implementation.

This package provides WebSocket consumers for implementing JSON-RPC 2.0 servers
using Django Channels.

Public API
----------
Consumers:
    - AsyncJsonRpcWebsocketConsumer: Async WebSocket JSON-RPC consumer
    - JsonRpcWebsocketConsumer: Sync WebSocket JSON-RPC consumer

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
"""

from channels_rpc.async_json_rpc_websocket_consumer import (
    AsyncJsonRpcWebsocketConsumer,
)
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
)

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
    "RequestTooLargeError",
]
