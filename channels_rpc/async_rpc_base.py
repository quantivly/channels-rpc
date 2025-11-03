from __future__ import annotations

import json
import logging
from collections.abc import Callable
from inspect import getfullargspec
from typing import TYPE_CHECKING, Any

from channels_rpc import logs
from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INTERNAL_ERROR,
    JsonRpcError,
    generate_error_response,
)
from channels_rpc.rpc_base import RpcBase, RpcMethodWrapper
from channels_rpc.utils import create_json_rpc_response

logger = logging.getLogger("django.channels.rpc")


class AsyncRpcBase(RpcBase):
    """Async base class for RPC consumers.

    This class extends RpcBase with async support. It should be mixed with an
    async Django Channels consumer class that provides the required async methods
    (send_json, send) and synchronous encode_json method. See
    AsyncChannelsConsumerProtocol for the expected interface.
    """

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

    async def execute_called_method(
        self, method: Callable | RpcMethodWrapper, params: dict | list
    ) -> Any:
        """Execute RPC method with appropriate parameter unpacking.

        Uses cached introspection result for optimal performance.

        Parameters
        ----------
        method : Callable | RpcMethodWrapper
            Method to execute.
        params : dict | list
            Parameters to pass.

        Returns
        -------
        Any
            Result from the method.
        """
        import asyncio  # noqa: PLC0415

        # Unwrap RpcMethodWrapper and get cached introspection result
        if isinstance(method, RpcMethodWrapper):
            actual_method = method.func
            accepts_consumer = method.accepts_consumer  # Use cached value
        else:
            # Fallback for raw callables (shouldn't happen in normal flow)
            actual_method = method
            spec = getfullargspec(actual_method)
            accepts_consumer = spec.varkw is not None

        # Execute with appropriate calling convention
        if isinstance(params, list):
            if accepts_consumer:
                result = actual_method(*params, consumer=self)
            else:
                result = actual_method(*params)
        elif accepts_consumer:
            result = actual_method(**params, consumer=self)
        else:
            result = actual_method(**params)

        # Await if the result is a coroutine
        if asyncio.iscoroutine(result):
            return await result
        return result

    async def process_call(  # type: ignore[override]
        self, data: dict[str, Any], *, is_notification: bool = False
    ) -> dict[str, Any] | None:
        method = self.get_method(data, is_notification=is_notification)
        params = self.get_params(data)
        rpc_id, _ = self.get_rpc_id(data)
        logger.debug("Executing %s(%s)", method.__qualname__, json.dumps(params))
        result = await self.execute_called_method(method, params)
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

    async def intercept_call(  # type: ignore[override]
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
        from channels_rpc.validation import validate_rpc_data  # noqa: PLC0415

        logger.debug("Intercepting call: %s", data)

        result: dict[str, Any] | None

        # Use shared validation logic
        error, is_response = validate_rpc_data(data)
        if error or is_response:
            return error or data, is_response

        # After validation, data is guaranteed to be a dict
        assert isinstance(data, dict)  # nosec B101 - Type assertion for mypy

        # Must be a JSON-RPC 2.0 request (or attempt)
        rpc_id = data.get("id")
        method_name = data.get("method")
        is_notification = rpc_id is None

        logger.debug(logs.CALL_INTERCEPTED, data)

        if rpc_id:
            logger.info(logs.RPC_METHOD_CALL_START, method_name, rpc_id)
        else:
            logger.info(logs.RPC_NOTIFICATION_START, method_name)

        try:
            result = await self.process_call(data, is_notification=is_notification)
        except JsonRpcError as e:
            # Re-raise JSON-RPC errors as-is
            result = e.as_dict()
        except (ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            # Expected application-level errors
            logger.info("Application error in RPC method: %s", e)
            result = generate_error_response(
                rpc_id=rpc_id,
                code=GENERIC_APPLICATION_ERROR,
                message="Application error occurred",
                data=None,  # Never leak internal details
            )
        except Exception:
            # Unexpected errors - these indicate bugs
            logger.exception("Unexpected error processing RPC call")
            result = generate_error_response(
                rpc_id=rpc_id,
                code=INTERNAL_ERROR,
                message="Internal server error",
                data=None,  # Never leak internal details
            )

        if rpc_id:
            logger.debug(logs.RPC_METHOD_CALL_END, rpc_id, method_name, result)
        else:
            logger.debug(logs.RPC_NOTIFICATION_END, method_name)

        return result, is_notification

    async def _base_receive_json(  # type: ignore[override]
        self, data: dict[str, Any]
    ) -> None:
        logger.debug("Received JSON: %s", data)
        result, is_notification = await self.intercept_call(data)
        if not is_notification:
            logger.debug("Sending result: %s", result)
            await self.send_json(result)
