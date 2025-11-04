from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from channels.db import database_sync_to_async
from django.db import transaction

from channels_rpc import logs
from channels_rpc.exceptions import (
    JsonRpcError,
    JsonRpcErrorCode,
    generate_error_response,
)
from channels_rpc.rpc_base import RpcBase, RpcMethodWrapper
from channels_rpc.utils import create_json_rpc_response

if TYPE_CHECKING:
    from channels_rpc.context import RpcContext

logger = logging.getLogger("channels_rpc")


class AsyncRpcBase(RpcBase):
    """Async base class for RPC consumers.

    This class extends RpcBase with async support. It should be mixed with an
    async Django Channels consumer class that provides the required async methods
    (send_json, send) and synchronous encode_json method. See
    AsyncChannelsConsumerProtocol for the expected interface.
    """

    @classmethod
    def database_rpc_method(
        cls,
        method_name: str | None = None,
        *,
        websocket: bool = True,
        atomic: bool = True,
        using: str | None = None,
    ) -> Callable:
        """Register an async RPC method that needs database access.

        This decorator combines rpc_method() with database_sync_to_async(),
        allowing the method to safely access Django ORM from async context.
        Optionally wraps the method in an atomic transaction.

        .. versionadded:: 1.0.0

        Parameters
        ----------
        method_name : str | None, optional
            Custom name for the method. If None, uses function __name__.
        websocket : bool, optional
            Enable for WebSocket transport, by default True.
        atomic : bool, optional
            Wrap method in atomic transaction, by default True.
        using : str | None, optional
            Database alias to use, by default None (uses default database).

        Returns
        -------
        Callable
            The decorated method.

        Examples
        --------
        With automatic transaction management::

            @MyConsumer.database_rpc_method()
            def create_user(username: str):
                user = User.objects.create(username=username)
                Profile.objects.create(user=user)  # Atomic with user creation
                return user.id

        Without transaction (read-only)::

            @MyConsumer.database_rpc_method(atomic=False)
            def get_stats():
                return User.objects.count()

        Using specific database::

            @MyConsumer.database_rpc_method(using='analytics')
            def log_event(event_data: dict):
                Event.objects.using('analytics').create(**event_data)

        With consumer context::

            @MyConsumer.database_rpc_method()
            def get_user(ctx: RpcContext, user_id: int) -> dict:
                # This can safely use Django ORM
                user = User.objects.get(id=user_id)
                return {"name": user.username, "email": user.email}

        Notes
        -----
        The decorated function should be synchronous (not async), as it will
        be automatically wrapped with database_sync_to_async. When atomic=True,
        the function is wrapped with transaction.atomic() before being converted
        to async, ensuring proper transaction management.
        """

        def decorator(func: Callable) -> Callable:
            from channels_rpc.decorators import inspect_accepts_context
            from channels_rpc.protocols import RpcMethodWrapper
            from channels_rpc.registry import get_registry

            # Inspect the original sync function BEFORE wrapping with database_sync_to_async
            name = method_name or func.__name__
            accepts_context = inspect_accepts_context(func)

            # Wrap with transaction if requested (BEFORE database_sync_to_async)
            wrapped_func = func
            if atomic:
                wrapped_func = transaction.atomic(using=using)(func)

            # Then wrap with database_sync_to_async for Django ORM access
            async_func = database_sync_to_async(wrapped_func)

            # Copy over function metadata
            async_func.__name__ = func.__name__
            async_func.__qualname__ = func.__qualname__
            if func.__doc__:
                async_func.__doc__ = func.__doc__

            # Create RpcMethodWrapper directly without re-inspection
            # (context inspection already done on sync function)
            wrapper = RpcMethodWrapper(
                func=async_func,
                options={"websocket": websocket},
                name=name,
                accepts_context=accepts_context,
            )
            registry = get_registry()
            registry.register_method(cls, name, wrapper)
            return wrapper

        return decorator

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
        import asyncio

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
        from channels_rpc.context import RpcContext

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

        logger.debug("Executing %s(%s)", method.__qualname__, json.dumps(params))
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
        from channels_rpc.validation import validate_rpc_data

        logger.debug("Intercepting call: %s", data)

        result: dict[str, Any] | None

        # Use shared validation logic
        error, is_response = validate_rpc_data(data)
        if error or is_response:
            return error or data, is_response

        # After validation, data is guaranteed to be a dict
        assert isinstance(data, dict)  # nosec B101 - Type assertion for mypy

        # Must be a JSON-RPC 2.0 request (or attempt)
        # Per JSON-RPC 2.0 spec:
        # - Notification: request WITHOUT "id" field
        # - Request with null ID: request WITH "id": null (must receive response)
        method_name = data.get("method")
        is_notification = "id" not in data
        rpc_id = data.get("id") if not is_notification else None

        logger.debug(logs.CALL_INTERCEPTED, data)

        if rpc_id:
            logger.info(logs.RPC_METHOD_CALL_START, method_name, rpc_id)
        else:
            logger.info(logs.RPC_NOTIFICATION_START, method_name)

        # Emit signal for method start
        import time

        from channels_rpc.signals import (
            rpc_method_failed,
            rpc_method_started,
        )

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
        for mw in self.middleware:
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
                    return (
                        generate_error_response(
                            rpc_id=rpc_id,
                            code=JsonRpcErrorCode.INVALID_REQUEST,
                            message="Request rejected by middleware",
                        ),
                        False,
                    )
                data = processed_data
            except JsonRpcError:
                # Let JSON-RPC errors propagate
                raise
            except Exception as e:
                # Catch middleware errors and convert to internal error
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
                result = generate_error_response(
                    rpc_id=rpc_id,
                    code=JsonRpcErrorCode.INTERNAL_ERROR,
                    message="Middleware error occurred",
                    data=None,
                )
                return result, is_notification

        try:
            result = await self._process_call(data, is_notification=is_notification)

            # Apply response middleware (in reverse order, only for non-notifications with results)
            if not is_notification and result is not None:
                for mw in reversed(self.middleware):
                    try:
                        processed_result = mw.process_response(result, self)
                        # Handle async middleware
                        if asyncio.iscoroutine(processed_result):
                            processed_result = await processed_result
                        result = processed_result
                    except Exception:
                        # Log middleware errors but continue with original response
                        logger.exception(
                            "Middleware error in process_response: %s",
                            mw.__class__.__name__,
                        )

            # Emit signal for successful completion
            from channels_rpc.signals import rpc_method_completed

            duration = time.time() - start_time
            rpc_method_completed.send(
                sender=self.__class__,
                consumer=self,
                method_name=method_name,
                result=result,
                rpc_id=rpc_id,
                duration=duration,
            )

        except JsonRpcError as e:
            # Re-raise JSON-RPC errors as-is
            duration = time.time() - start_time
            rpc_method_failed.send(
                sender=self.__class__,
                consumer=self,
                method_name=method_name,
                error=e,
                rpc_id=rpc_id,
                duration=duration,
            )
            result = e.as_dict()
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            # Expected application-level errors (domain logic errors)
            # Note: RuntimeError intentionally NOT caught here - it indicates bugs
            logger.info("Application error in RPC method: %s", e)
            duration = time.time() - start_time
            rpc_method_failed.send(
                sender=self.__class__,
                consumer=self,
                method_name=method_name,
                error=e,
                rpc_id=rpc_id,
                duration=duration,
            )
            result = generate_error_response(
                rpc_id=rpc_id,
                code=JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
                message="Application error occurred",
                data=None,  # Never leak internal details
            )
        except Exception as e:
            # Unexpected errors - these indicate bugs
            logger.exception("Unexpected error processing RPC call")
            duration = time.time() - start_time
            rpc_method_failed.send(
                sender=self.__class__,
                consumer=self,
                method_name=method_name,
                error=e,
                rpc_id=rpc_id,
                duration=duration,
            )
            result = generate_error_response(
                rpc_id=rpc_id,
                code=JsonRpcErrorCode.INTERNAL_ERROR,
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
        result, is_notification = await self._intercept_call(data)
        if not is_notification:
            logger.debug("Sending result: %s", result)
            await self.send_json(result)
