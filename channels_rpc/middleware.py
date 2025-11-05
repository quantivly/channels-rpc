"""Middleware support for RPC request/response processing.

This module provides a protocol-based middleware system that allows intercepting
RPC requests before execution and responses before transmission. This enables
implementing cross-cutting concerns without modifying individual RPC methods.

Examples
--------
Basic middleware implementation::

    from channels_rpc.middleware import RpcMiddleware
    from channels_rpc.exceptions import JsonRpcError, JsonRpcErrorCode

    class RateLimitMiddleware:
        def __init__(self):
            self.call_counts = {}

        def process_request(self, data, consumer):
            method = data.get('method')
            # Check rate limit
            count = self.call_counts.get(method, 0)
            if count > 100:
                raise JsonRpcError(
                    data.get('id'),
                    JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
                    data={'error': 'Rate limit exceeded'}
                )
            self.call_counts[method] = count + 1
            return data

        def process_response(self, response, consumer):
            # Add metadata to response
            response['_server'] = 'my-server'
            return response

Using middleware in consumers::

    from channels_rpc import AsyncJsonRpcWebsocketConsumer
    from my_app.middleware import RateLimitMiddleware, LoggingMiddleware

    class MyConsumer(AsyncJsonRpcWebsocketConsumer):
        # Middleware is applied in order
        middleware = [
            LoggingMiddleware(),
            RateLimitMiddleware(),
        ]

        @MyConsumer.rpc_method()
        def get_data(self, resource_id: int):
            return {'data': 'value'}

Async middleware support::

    class AsyncAuthMiddleware:
        async def process_request(self, data, consumer):
            # Async validation
            token = data.get('params', {}).get('token')
            if not await self.verify_token(token):
                raise JsonRpcError(
                    data.get('id'),
                    JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
                    data={'error': 'Invalid token'}
                )
            return data

        async def process_response(self, response, consumer):
            # Can also be async
            return response

Notes
-----
.. versionadded:: 1.1.0
   Added middleware support for cross-cutting concerns.
"""

from __future__ import annotations

import logging
from typing import Any, Protocol

logger = logging.getLogger("channels_rpc.middleware")


class RpcMiddleware(Protocol):
    """Protocol for RPC middleware components.

    Middleware can intercept requests before execution and responses
    after execution to add cross-cutting concerns like logging, authentication,
    rate limiting, caching, and metrics collection.

    Methods can be synchronous or asynchronous. The framework will automatically
    detect and handle coroutines returned from async methods.

    Methods
    -------
    process_request(data, consumer)
        Called before RPC method execution. Can modify request data,
        reject requests by returning None, or raise JsonRpcError.

    process_response(response, consumer)
        Called after successful RPC method execution, before sending
        response to client. Can modify the response data.

    Examples
    --------
    Implement request validation middleware::

        class ValidationMiddleware:
            def process_request(self, data, consumer):
                # Validate required fields
                if 'method' not in data:
                    raise JsonRpcError(
                        data.get('id'),
                        JsonRpcErrorCode.INVALID_REQUEST
                    )
                return data

            def process_response(self, response, consumer):
                return response

    Implement async authentication middleware::

        class AuthMiddleware:
            async def process_request(self, data, consumer):
                token = data.get('params', {}).get('token')
                if not await self.validate_token(token):
                    return None  # Reject request
                return data

            def process_response(self, response, consumer):
                return response

    Notes
    -----
    - Middleware is applied in the order defined in the consumer's middleware list
    - Response middleware is applied in reverse order (LIFO)
    - If process_request returns None, the request is rejected with an error
    - Raising JsonRpcError allows custom error responses
    - Other exceptions are caught and converted to INTERNAL_ERROR responses
    """

    def process_request(
        self, data: dict[str, Any], consumer: Any  # noqa: ARG002
    ) -> dict[str, Any] | None:
        """Process request before method execution.

        This method is called before the RPC method is executed. It can:
        - Inspect and modify the request data
        - Validate request parameters
        - Enforce access control or rate limiting
        - Reject requests by returning None
        - Raise JsonRpcError for custom error responses

        Parameters
        ----------
        data : dict[str, Any]
            The JSON-RPC request data containing:
            - jsonrpc: Version string ("2.0")
            - method: Method name
            - params: Method parameters (if present)
            - id: Request ID (if not a notification)
        consumer : RpcBase
            The consumer instance handling this request. Provides access
            to scope, send methods, and other consumer functionality.

        Returns
        -------
        dict[str, Any] | None
            Modified request data to continue processing, or None to
            reject the request with a generic error response.

        Raises
        ------
        JsonRpcError
            To send a custom error response to the client.
        """
        return data

    def process_response(
        self, response: dict[str, Any], consumer: Any  # noqa: ARG002
    ) -> dict[str, Any]:
        """Process response before sending to client.

        This method is called after successful RPC method execution, before
        the response is sent to the client. It can:
        - Inspect and modify the response data
        - Add metadata or headers
        - Log response details
        - Transform result format

        Note that this is only called for successful responses, not for
        error responses generated by exceptions.

        Parameters
        ----------
        response : dict[str, Any]
            The JSON-RPC response data containing:
            - jsonrpc: Version string ("2.0")
            - result: Method return value
            - id: Request ID
        consumer : RpcBase
            The consumer instance handling this request.

        Returns
        -------
        dict[str, Any]
            Modified response data to send to client.
        """
        return response


class LoggingMiddleware:
    """Example middleware that logs RPC calls.

    This middleware logs each RPC method call with timing information.
    Useful for debugging and monitoring API usage.

    Examples
    --------
    Basic usage::

        class MyConsumer(AsyncJsonRpcWebsocketConsumer):
            middleware = [LoggingMiddleware()]

    Custom logger::

        class MyConsumer(AsyncJsonRpcWebsocketConsumer):
            middleware = [
                LoggingMiddleware(logger_name="my_app.rpc")
            ]

    Parameters
    ----------
    logger_name : str, optional
        Name of the logger to use, by default "channels_rpc.middleware".
    log_params : bool, optional
        Whether to log request parameters, by default False. Enable with
        caution as params may contain sensitive data.
    """

    def __init__(
        self,
        logger_name: str = "channels_rpc.middleware",
        *,
        log_params: bool = False,
    ):
        """Initialize LoggingMiddleware.

        Parameters
        ----------
        logger_name : str, optional
            Name of the logger to use.
        log_params : bool, optional
            Whether to log request parameters.
        """
        self.logger = logging.getLogger(logger_name)
        self.log_params = log_params

    def process_request(
        self, data: dict[str, Any], consumer: Any  # noqa: ARG002
    ) -> dict[str, Any]:
        """Log RPC method call.

        Parameters
        ----------
        data : dict[str, Any]
            Request data.
        consumer : Any
            Consumer instance.

        Returns
        -------
        dict[str, Any]
            Unmodified request data.
        """
        method = data.get("method", "unknown")
        rpc_id = data.get("id", "notification")

        if self.log_params:
            params = data.get("params", {})
            self.logger.info(
                "RPC call: method=%s id=%s params=%s", method, rpc_id, params
            )
        else:
            self.logger.info("RPC call: method=%s id=%s", method, rpc_id)

        return data

    def process_response(
        self, response: dict[str, Any], consumer: Any  # noqa: ARG002
    ) -> dict[str, Any]:
        """Log RPC method response.

        Parameters
        ----------
        response : dict[str, Any]
            Response data.
        consumer : Any
            Consumer instance.

        Returns
        -------
        dict[str, Any]
            Unmodified response data.
        """
        rpc_id = response.get("id", "unknown")
        self.logger.debug("RPC response: id=%s", rpc_id)
        return response
