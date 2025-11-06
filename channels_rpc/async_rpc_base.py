from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from channels_rpc import logs
from channels_rpc.context import RpcContext
from channels_rpc.exceptions import (
    JsonRpcError,
    JsonRpcErrorCode,
    generate_error_response,
)
from channels_rpc.protocols import RpcMethodWrapper
from channels_rpc.rpc_base import RpcBase
from channels_rpc.signals import (
    rpc_method_completed,
    rpc_method_failed,
    rpc_method_started,
)
from channels_rpc.utils import create_json_rpc_response
from channels_rpc.validation import validate_rpc_data

logger = logging.getLogger("channels_rpc")

# Default maximum execution time for RPC methods (5 minutes)
# This prevents DoS attacks from long-running methods
# Can be overridden per-method using the timeout parameter
MAX_METHOD_EXECUTION_TIME = 300

# Maximum allowed length for request IDs (in characters)
# Prevents DoS attacks via extremely long ID strings
# Malicious clients could send IDs of 100MB+ which would:
# - Consume excessive memory
# - Slow down ID lookups and comparisons
# - Fill up logs and monitoring systems
MAX_REQUEST_ID_LENGTH = 256


class AsyncRpcBase(RpcBase):
    """Async base class for RPC consumers.

    This class extends RpcBase with async support. It should be mixed with an
    async Django Channels consumer class that provides the required async methods
    (send_json, send) and synchronous encode_json method. See
    AsyncChannelsConsumerProtocol for the expected interface.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize the async RPC consumer with request ID collision tracking."""
        super().__init__(*args, **kwargs)

        # Request ID collision detection
        # Tracks recent request IDs with timestamps to prevent replay attacks
        self._recent_request_ids: dict[str | int, float] = {}
        self._request_id_cooldown = 10.0  # seconds

    if TYPE_CHECKING:
        # Async type hints for methods provided by Channels consumer mixin
        # These override the sync versions in RpcBase for async consumers
        scope: dict[str, Any]

        async def send_json(  # type: ignore[override]
            self, content: dict[str, Any], close: bool = False  # noqa: FBT001, FBT002
        ) -> None:
            """Send JSON data to the client asynchronously."""
            ...

        async def send(  # type: ignore[override]
            self,
            text_data: str | None = None,
            bytes_data: bytes | None = None,
            close: bool = False,  # noqa: FBT001, FBT002
        ) -> None:
            """Send text or binary data to the client asynchronously."""
            ...

        def encode_json(self, content: dict[str, Any]) -> str:
            """Encode a dict as JSON."""
            ...

    async def _execute_called_method(
        self,
        method: Callable | RpcMethodWrapper,
        params: dict | list,
        context: RpcContext,
    ) -> Any:
        """Execute RPC method with appropriate parameter unpacking.

        Uses cached introspection result for optimal performance.

        Parameters
        ----------
        method : Callable | RpcMethodWrapper
            Method to execute.
        params : dict | list
            Parameters to pass.
        context : RpcContext
            Execution context to pass if method accepts it.

        Returns
        -------
        Any
            Result from the method.
        """
        # Unwrap RpcMethodWrapper and get cached introspection result
        if isinstance(method, RpcMethodWrapper):
            actual_method = method.func
            accepts_context = method.accepts_context  # Use cached value
        else:
            # Fallback for raw callables (shouldn't happen in normal flow)
            actual_method = method
            accepts_context = False

        # Execute with appropriate calling convention
        if accepts_context:
            if isinstance(params, list):
                result = actual_method(context, *params)
            else:
                result = actual_method(context, **params)
        elif isinstance(params, list):
            result = actual_method(*params)
        else:
            result = actual_method(**params)

        # Await if the result is a coroutine
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def _process_call(  # type: ignore[override]
        self, data: dict[str, Any], *, is_notification: bool = False
    ) -> dict[str, Any] | None:
        from channels_rpc.context import RpcContext  # noqa: PLC0415

        method = self._get_method(data, is_notification=is_notification)
        params = self._get_params(data)
        rpc_id, _ = self._get_rpc_id(data)
        method_name = data["method"]

        # Create execution context
        context = RpcContext(
            consumer=self,
            method_name=method_name,
            rpc_id=rpc_id,
            is_notification=is_notification,
        )

        # Determine timeout for this method
        # Use method-specific timeout if set, otherwise use default
        method_timeout: float | None = None
        if isinstance(method, RpcMethodWrapper):
            method_timeout = method.timeout

        # Use method timeout if specified, otherwise use default
        # Timeout values <= 0 disable timeout enforcement
        timeout: float | None
        if method_timeout is None:
            timeout = float(MAX_METHOD_EXECUTION_TIME)
        elif method_timeout <= 0:
            timeout = None  # Disable timeout
        else:
            timeout = method_timeout

        logger.debug("Executing %s(%s)", method.__qualname__, json.dumps(params))

        # Execute method with timeout enforcement
        if timeout is not None:
            try:
                result = await asyncio.wait_for(
                    self._execute_called_method(method, params, context),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                # Log timeout for monitoring
                logger.error(
                    "RPC method %s timed out after %.1f seconds (rpc_id=%s)",
                    method_name,
                    timeout,
                    rpc_id,
                )
                # Re-raise as JsonRpcError with appropriate error code
                # Include timeout duration in data for informative error message
                raise JsonRpcError(
                    rpc_id=rpc_id,
                    code=JsonRpcErrorCode.INTERNAL_ERROR,
                    data={"timeout": timeout},
                ) from None
        else:
            # No timeout enforcement
            result = await self._execute_called_method(method, params, context)

        if not is_notification:
            logger.debug("Execution result: %s", result)
            # Return standard JSON-RPC 2.0 response
            response = create_json_rpc_response(
                rpc_id=rpc_id,
                result=result,
                compressed=False,
            )
            return response
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning("method: %s, params: %s", method.__qualname__, params)
            result = None
        return result

    def _check_request_id_collision(self, rpc_id: str | int | None) -> None:
        """Check for request ID collisions and enforce cooldown period.

        Tracks request IDs with timestamps to detect reuse within cooldown period.
        This prevents clients from reusing IDs too quickly, which could cause
        issues with request tracking and response routing.

        Parameters
        ----------
        rpc_id : str | int | None
            Request ID to check for collisions. None is allowed (notifications).

        Raises
        ------
        JsonRpcError
            If the request ID was used within the cooldown period.

        Notes
        -----
        The tracking dictionary is automatically pruned when it exceeds 10,000 entries
        to prevent unbounded memory growth.
        """
        if rpc_id is None:
            return  # Notifications don't have IDs, no collision possible

        # Lazy initialization for Django Channels consumers that don't call __init__
        if not hasattr(self, "_recent_request_ids"):
            self._recent_request_ids = {}  # Type already defined in __init__
            self._request_id_cooldown = 10.0

        current_time = time.time()

        # Clean old IDs periodically to keep dict bounded
        if len(self._recent_request_ids) > 10000:
            cutoff = current_time - self._request_id_cooldown
            self._recent_request_ids = {
                k: v for k, v in self._recent_request_ids.items() if v >= cutoff
            }

        # Check for collision
        if rpc_id in self._recent_request_ids:
            last_used = self._recent_request_ids[rpc_id]
            if current_time - last_used < self._request_id_cooldown:
                raise JsonRpcError(
                    rpc_id,
                    JsonRpcErrorCode.INVALID_REQUEST,
                    data={
                        "error": f"Request ID '{rpc_id}' reused within cooldown period",
                        "cooldown_seconds": self._request_id_cooldown,
                    },
                )

        # Record this ID
        self._recent_request_ids[rpc_id] = current_time

    def _validate_request_id(
        self, rpc_id: str | int | float | None
    ) -> tuple[dict[str, Any] | None, bool]:
        """Validate request ID length to prevent DoS attacks.

        Parameters
        ----------
        rpc_id : str | int | float | None
            Request ID to validate.

        Returns
        -------
        tuple[dict[str, Any] | None, bool]
            Error response and False if invalid, or (None, False) if valid.
        """
        if rpc_id is not None:
            rpc_id_str = str(rpc_id)
            if len(rpc_id_str) > MAX_REQUEST_ID_LENGTH:
                # Don't echo back the long ID in the error response
                # Use None as rpc_id to avoid consuming memory with malicious payload
                logger.warning(
                    f"Rejecting request with oversized ID: {len(rpc_id_str)} chars "
                    f"(max: {MAX_REQUEST_ID_LENGTH}). Possible DoS attempt."
                )
                return (
                    generate_error_response(
                        rpc_id=None,  # Don't echo back long ID
                        code=JsonRpcErrorCode.INVALID_REQUEST,
                        message=(
                            f"Request ID too long "
                            f"(max: {MAX_REQUEST_ID_LENGTH} chars)"
                        ),
                    ),
                    False,
                )
        return None, False

    async def _apply_request_middleware(  # type: ignore[override]
        self,
        data: dict[str, Any],
        rpc_id: str | int | float | None,
        method_name: str,
        start_time: float,
        is_notification: bool,  # noqa: FBT001, ARG002
    ) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """Apply request middleware chain.

        Parameters
        ----------
        data : dict[str, Any]
            Request data to process.
        rpc_id : str | int | float | None
            Request ID for error responses.
        method_name : str
            Method name for error reporting.
        start_time : float
            Start time for duration calculation.
        is_notification : bool
            Whether this is a notification.

        Returns
        -------
        tuple[dict[str, Any] | None, dict[str, Any] | None]
            (processed_data, error_response). If error_response is not None,
            processing should stop and return the error.
        """
        for mw in self.middleware or []:
            try:
                processed_data = mw.process_request(data, self)
                # Handle async middleware
                if asyncio.iscoroutine(processed_data):
                    processed_data = await processed_data
                if processed_data is None:
                    # Middleware rejected request
                    logger.warning(
                        "Request rejected by middleware: %s", mw.__class__.__name__
                    )
                    error = generate_error_response(
                        rpc_id=rpc_id,
                        code=JsonRpcErrorCode.INVALID_REQUEST,
                        message="Request rejected by middleware",
                    )
                    return None, error
                data = processed_data
            except JsonRpcError:
                # Let JSON-RPC errors propagate
                raise
            except Exception as e:
                # Catch middleware errors and convert to internal error
                from channels_rpc.config import get_config  # noqa: PLC0415

                config = get_config()

                if config.sanitize_errors:
                    logger.error(
                        "Middleware error in process_request: %s - %s: %s",
                        mw.__class__.__name__,
                        type(e).__name__,
                        str(e)[:200],  # Truncate to avoid leaking sensitive data
                    )
                else:
                    logger.exception(
                        "Middleware error in process_request: %s", mw.__class__.__name__
                    )
                duration = time.time() - start_time
                rpc_method_failed.send(
                    sender=self.__class__,
                    consumer=self,
                    method_name=method_name,
                    error=e,
                    rpc_id=rpc_id,
                    duration=duration,
                )
                error = generate_error_response(
                    rpc_id=rpc_id,
                    code=JsonRpcErrorCode.INTERNAL_ERROR,
                    message="Middleware error occurred",
                    data=None,
                )
                return None, error
        return data, None

    async def _apply_response_middleware(  # type: ignore[override]
        self, result: dict[str, Any] | None, is_notification: bool  # noqa: FBT001
    ) -> dict[str, Any] | None:
        """Apply response middleware chain in reverse order.

        Parameters
        ----------
        result : dict[str, Any] | None
            Response data to process.
        is_notification : bool
            Whether this is a notification.

        Returns
        -------
        dict[str, Any] | None
            Processed response.
        """
        if not is_notification and result is not None:
            for mw in reversed(self.middleware or []):
                try:
                    processed_result = mw.process_response(result, self)
                    # Handle async middleware
                    if asyncio.iscoroutine(processed_result):
                        processed_result = await processed_result
                    result = processed_result
                except Exception as e:
                    # Log middleware errors but continue with original response
                    from channels_rpc.config import get_config  # noqa: PLC0415

                    config = get_config()

                    if config.sanitize_errors:
                        logger.error(
                            "Middleware error in process_response: %s - %s: %s",
                            mw.__class__.__name__,
                            type(e).__name__,
                            str(e)[:200],
                        )
                    else:
                        logger.exception(
                            "Middleware error in process_response: %s",
                            mw.__class__.__name__,
                        )
        return result

    def _handle_rpc_exception(
        self,
        exception: Exception,
        rpc_id: str | int | float | None,
        method_name: str,
        start_time: float,
    ) -> dict[str, Any]:
        """Handle exceptions during RPC method execution.

        Parameters
        ----------
        exception : Exception
            Exception that was raised.
        rpc_id : str | int | float | None
            Request ID for error response.
        method_name : str
            Method name for error reporting.
        start_time : float
            Start time for duration calculation.

        Returns
        -------
        dict[str, Any]
            Error response.
        """
        duration = time.time() - start_time
        rpc_method_failed.send(
            sender=self.__class__,
            consumer=self,
            method_name=method_name,
            error=exception,
            rpc_id=rpc_id,
            duration=duration,
        )

        if isinstance(exception, JsonRpcError):
            # Re-raise JSON-RPC errors as-is
            return exception.as_dict()
        elif isinstance(exception, ValueError | TypeError | KeyError | AttributeError):
            # Expected application-level errors (domain logic errors)
            # Note: RuntimeError intentionally NOT caught here - it indicates bugs
            logger.info("Application error in RPC method: %s", exception)
            return generate_error_response(
                rpc_id=rpc_id,
                code=JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
                message="Application error occurred",
                data=None,  # Never leak internal details
            )
        else:
            # Unexpected errors - these indicate bugs
            # Check if we should sanitize errors (production mode)
            from channels_rpc.config import get_config  # noqa: PLC0415

            config = get_config()

            if config.sanitize_errors:
                # Production: Log without stack trace to avoid information disclosure
                logger.error(
                    "Unexpected error processing RPC call '%s': %s",
                    method_name,
                    f"{type(exception).__name__}: {str(exception)[:200]}",
                )
            else:
                # Development mode: Log with full stack trace for debugging
                logger.exception("Unexpected error processing RPC call")

            return generate_error_response(
                rpc_id=rpc_id,
                code=JsonRpcErrorCode.INTERNAL_ERROR,
                message="Internal server error",
                data=None,  # Never leak internal details
            )

    async def _intercept_call(  # type: ignore[override]
        self, data: dict[str, Any] | list[dict[str, Any]] | None
    ) -> tuple[Any, bool]:
        """Handle JSON-RPC 2.0 requests and responses.

        Parameters
        ----------
        data : dict[str, Any] | list[dict[str, Any]] | None
            JSON-RPC 2.0 message data.

        Returns
        -------
        tuple[Any, bool]
            Result and whether it's a notification.
        """
        logger.debug("Intercepting call: %s", data)

        result: dict[str, Any] | None

        # Use shared validation logic
        error, is_response = validate_rpc_data(data)
        if error or is_response:
            return error or data, is_response

        # After validation, data is guaranteed to be a dict
        # This should never fail, but check for type safety
        if not isinstance(data, dict):
            error_msg = f"Expected dict after validation, got {type(data).__name__}"
            raise TypeError(error_msg)

        # Must be a JSON-RPC 2.0 request (or attempt)
        # Per JSON-RPC 2.0 spec:
        # - Notification: request WITHOUT "id" field
        # - Request with null ID: request WITH "id": null (must receive response)
        method_name = data.get("method")
        is_notification = "id" not in data
        rpc_id = data.get("id") if not is_notification else None

        # Type narrowing: method_name should be str after validation
        # Use cast for flexibility
        if not isinstance(method_name, str):
            method_name = str(method_name) if method_name is not None else ""

        # Validate request ID length to prevent DoS attacks
        error_response, should_return = self._validate_request_id(rpc_id)
        if error_response is not None:
            return error_response, should_return

        # Check for request ID collisions (prevents replay attacks)
        try:
            self._check_request_id_collision(rpc_id)
        except JsonRpcError as e:
            logger.warning(
                "Request ID collision detected: %s",
                e.data.get("error") if e.data else "unknown",
            )
            return e.as_dict(), False

        logger.debug(logs.CALL_INTERCEPTED, data)

        if rpc_id:
            logger.info(logs.RPC_METHOD_CALL_START, method_name, rpc_id)
        else:
            logger.info(logs.RPC_NOTIFICATION_START, method_name)

        # Emit signal for method start
        start_time = time.time()
        params = data.get("params", {})

        rpc_method_started.send(
            sender=self.__class__,
            consumer=self,
            method_name=method_name,
            params=params,
            rpc_id=rpc_id,
        )

        # Apply request middleware
        data, error = await self._apply_request_middleware(
            data, rpc_id, method_name, start_time, is_notification
        )
        if error is not None:
            return error, is_notification

        # Type narrowing: If error is None, data must be valid
        # Note: Using explicit checks instead of assert for production safety
        # (asserts are removed with -O optimization flag)
        if data is None:
            logger.error(
                "Middleware returned None for both data and error - this indicates a "
                "middleware bug. Method: %s, RPC ID: %s",
                method_name,
                rpc_id,
            )
            return (
                generate_error_response(
                    rpc_id=rpc_id,
                    code=JsonRpcErrorCode.INTERNAL_ERROR,
                    message="Internal server error",
                    data={"error": "Request data missing after middleware processing"},
                ),
                is_notification,
            )

        if not isinstance(method_name, str):
            logger.error(
                "method_name is not a string after validation: %s (type: %s)",
                method_name,
                type(method_name).__name__,
            )
            return (
                generate_error_response(
                    rpc_id=rpc_id,
                    code=JsonRpcErrorCode.INTERNAL_ERROR,
                    message="Internal server error",
                    data={"error": "Invalid method name type"},
                ),
                is_notification,
            )

        try:
            result = await self._process_call(data, is_notification=is_notification)

            # Apply response middleware (reverse order, non-notifications)
            result = await self._apply_response_middleware(result, is_notification)

            # Emit signal for successful completion
            duration = time.time() - start_time
            rpc_method_completed.send(
                sender=self.__class__,
                consumer=self,
                method_name=method_name,
                result=result,
                rpc_id=rpc_id,
                duration=duration,
            )

        except (
            JsonRpcError,
            ValueError,
            TypeError,
            KeyError,
            AttributeError,
        ) as e:
            # Handle application-level errors only
            # Note: Exception removed from tuple to avoid masking system exceptions
            # Unexpected errors will propagate and be logged by outer error handlers
            result = self._handle_rpc_exception(e, rpc_id, method_name, start_time)

        if rpc_id:
            logger.debug(logs.RPC_METHOD_CALL_END, rpc_id, method_name, result)
        else:
            logger.debug(logs.RPC_NOTIFICATION_END, method_name)

        return result, is_notification

    async def _base_receive_json(  # type: ignore[override]
        self, data: dict[str, Any]
    ) -> None:
        logger.debug("Received JSON: %s", data)
        result, is_notification = await self._intercept_call(data)
        if not is_notification:
            logger.debug("Sending result: %s", result)
            await self.send_json(result)
