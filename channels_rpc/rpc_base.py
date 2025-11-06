"""Definition of the :class:`RpcBase` class.

A JSON-RPC request message can contain three possible elements: The *method*, which
is a string that names the method to be invoked; *params*, which are objects or arrays
of values that get passed along as parameters to the destination app; and *id*, a
string or number that matches the response with the request that it is replying to.

References
----------
- https://nonamesecurity.com/learn/what-is-json-rpc/
"""

from __future__ import annotations

import inspect
import json
import logging
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from channels_rpc import logs
from channels_rpc.context import RpcContext
from channels_rpc.decorators import create_rpc_method_wrapper
from channels_rpc.exceptions import (
    JsonRpcError,
    JsonRpcErrorCode,
    generate_error_response,
)
from channels_rpc.limits import check_size_limits
from channels_rpc.protocols import MethodInfo, RpcMethodWrapper
from channels_rpc.registry import get_registry
from channels_rpc.signals import (
    rpc_method_completed,
    rpc_method_failed,
    rpc_method_started,
)
from channels_rpc.utils import create_json_rpc_request, create_json_rpc_response
from channels_rpc.validation import validate_rpc_data

if TYPE_CHECKING:
    from channels_rpc.middleware import RpcMiddleware

logger = logging.getLogger("channels_rpc")


class RpcBase:
    """Base class for RPC consumers.

    Variant of WebsocketConsumer that automatically JSON-encodes and decodes
    messages as they come in and go out. Expects everything to be text; will
    error on binary data.

    This class should be mixed with a Django Channels consumer class that
    provides the required methods (send_json, send, encode_json) and attributes
    (scope). See ChannelsConsumerProtocol for the expected interface.

    Errors:

    - -32700
      Parse error
      Invalid JSON was received by the server.
      An error occurred on the server while parsing the JSON text.

    - -32600
      Invalid Request
      The JSON sent is not a valid Request object.

    - -32601
      Method not found
      The method does not exist / is not available.

    - -32602
      Invalid params
      Invalid method parameter(s).

    - -32603
      Internal error
      Internal JSON-RPC error.

    - -32099 to -32000
      Server error
      Reserved for implementation-defined server-errors. (@TODO)

    Attributes
    ----------
    middleware : list[RpcMiddleware]
        List of middleware instances to apply to RPC requests and responses.
        Middleware is applied in order for requests, and in reverse order for
        responses. See middleware module for details.

    References
    ----------
    - http://groups.google.com/group/json-rpc/web/json-rpc-2-0
    """

    # Class-level middleware list (can be overridden by subclasses)
    # Default to None to avoid mutable default argument bug
    middleware: list[RpcMiddleware] | None = None

    if TYPE_CHECKING:
        # Type hints for methods provided by Channels consumer mixin
        # These are defined in ChannelsConsumerProtocol
        scope: dict[str, Any]

        def send_json(
            self, content: dict[str, Any], close: bool = False  # noqa: FBT001, FBT002
        ) -> None:
            """Send JSON data to the client."""
            ...

        def send(
            self,
            text_data: str | None = None,
            bytes_data: bytes | None = None,
            close: bool = False,  # noqa: FBT001, FBT002
        ) -> None:
            """Send text or binary data to the client."""
            ...

        def encode_json(self, content: dict[str, Any]) -> str:
            """Encode a dict as JSON."""
            ...

    @classmethod
    def rpc_method(
        cls,
        method_name: str | None = None,
        *,
        websocket: bool = True,
        timeout: float | None = None,
    ) -> Callable:
        """A decorator for registering RPC methods.

        Parameters
        ----------
        method_name : str, optional
            RPC method name for the function, by default None.
        websocket : bool, optional
            Whether WebSocket transport can use this function, by default True.
        timeout : float | None, optional
            Maximum execution time in seconds. If None, uses default timeout
            (300 seconds). Set to 0 or negative to disable timeout.
            By default None.

        Returns
        -------
        Callable
            Decorated function.

        Notes
        -----
        .. versionchanged:: 1.0.0
            Removed `http` parameter. HTTP transport is no longer supported.
        .. versionchanged:: 1.1.0
            Added `timeout` parameter for method execution timeout.
        """

        def wrap(method: Callable) -> RpcMethodWrapper:
            name = method_name or method.__name__

            # Use shared decorator logic to create wrapper
            wrapper = create_rpc_method_wrapper(
                func=method,
                name=name,
                options={"websocket": websocket},
                timeout=timeout,
            )

            registry = get_registry()
            registry.register_method(cls, name, wrapper)
            return wrapper

        return wrap

    @classmethod
    def get_rpc_methods(cls) -> list[str]:
        """List RPC methods available for this consumer.
        Returns a list of all registered RPC method names for this consumer class.
        This is useful for introspection, debugging, and building dynamic client
        interfaces.

        Returns
        -------
        list[str]
            List of RPC methods available for this consumer.

        Examples
        --------
        Introspect available methods::

            class MyConsumer(JsonRpcWebsocketConsumer):
                @JsonRpcWebsocketConsumer.rpc_method()
                def get_user(self, user_id: int):
                    return {"user": {"id": user_id, "name": "John"}}

                @JsonRpcWebsocketConsumer.rpc_method()
                def list_users(self):
                    return {"users": []}

            # Get list of available methods
            methods = MyConsumer.get_rpc_methods()
            # Returns: ["get_user", "list_users"]

        Implement a discovery endpoint::

            class ApiConsumer(JsonRpcWebsocketConsumer):
                @JsonRpcWebsocketConsumer.rpc_method()
                def discover(self):
                    \"\"\"Return list of available RPC methods.\"\"\"
                    methods = self.__class__.get_rpc_methods()
                    return {
                        "methods": methods,
                        "version": "1.0",
                        "server": "channels-rpc"
                    }

                @JsonRpcWebsocketConsumer.rpc_method()
                def get_data(self, resource_id: int):
                    return {"data": {}}

        Build dynamic test suite::

            import pytest

            def test_all_methods_documented():
                methods = MyConsumer.get_rpc_methods()
                for method_name in methods:
                    method = getattr(MyConsumer, method_name)
                    assert method.__doc__, f"{method_name} is missing docstring"
        """
        registry = get_registry()
        return registry.list_method_names(cls)

    @classmethod
    def rpc_notification(
        cls,
        notification_name: str | None = None,
        *,
        websocket: bool = True,
    ) -> Callable:
        """A decorator for registering RPC notifications.

        Parameters
        ----------
        notification_name : str, optional
            RPC name for the function, by default None.
        websocket : bool, optional
            Whether WebSocket transport can use this function, by default True.

        Returns
        -------
        Callable
            Decorated function.

        Notes
        -----
        .. versionchanged:: 1.0.0
            Removed `http` parameter. HTTP transport is no longer supported.
        """

        def wrap(method: Callable) -> RpcMethodWrapper:
            name = notification_name or method.__name__

            # Use shared decorator logic to create wrapper
            wrapper = create_rpc_method_wrapper(
                func=method,
                name=name,
                options={"websocket": websocket},
            )

            registry = get_registry()
            registry.register_notification(cls, name, wrapper)
            return wrapper

        return wrap

    @classmethod
    def get_rpc_notifications(cls) -> list[str]:
        """List RPC notifications available for this consumer.
        Returns a list of all registered RPC notification handler names for this
        consumer class. Notifications are one-way messages that do not expect a
        response.

        Returns
        -------
        list[str]
            List of RPC notifications available for this consumer.

        Examples
        --------
        Introspect available notification handlers::

            class MyConsumer(JsonRpcWebsocketConsumer):
                @JsonRpcWebsocketConsumer.rpc_notification()
                def client_heartbeat(self, timestamp: float):
                    self.last_heartbeat = timestamp
                    logger.info(f"Heartbeat received at {timestamp}")

                @JsonRpcWebsocketConsumer.rpc_notification()
                def client_status_update(self, status: str):
                    logger.info(f"Client status: {status}")

            # Get list of notification handlers
            notifications = MyConsumer.get_rpc_notifications()
            # Returns: ["client_heartbeat", "client_status_update"]

        Build comprehensive API documentation::

            class DocumentedConsumer(JsonRpcWebsocketConsumer):
                @classmethod
                def get_api_spec(cls):
                    \"\"\"Generate API specification for this consumer.\"\"\"
                    return {
                        "methods": cls.get_rpc_methods(),
                        "notifications": cls.get_rpc_notifications(),
                        "version": "1.0.0"
                    }

                @JsonRpcWebsocketConsumer.rpc_method()
                def get_status(self):
                    return {"status": "ok"}

                @JsonRpcWebsocketConsumer.rpc_notification()
                def log_event(self, event: dict):
                    logger.info(f"Event: {event}")

        Validate client capabilities::

            class ValidatingConsumer(JsonRpcWebsocketConsumer):
                def connect(self):
                    self.accept()
                    # Send list of supported notifications to client
                    self.send_json({
                        "type": "capabilities",
                        "supported_notifications": self.get_rpc_notifications()
                    })

                @JsonRpcWebsocketConsumer.rpc_notification()
                def client_ready(self):
                    logger.info("Client is ready")
        """
        registry = get_registry()
        return list(registry.get_notifications(cls).keys())

    @classmethod
    def get_method_info(cls, method_name: str) -> MethodInfo:
        """Get detailed information about a registered RPC method.

        Parameters
        ----------
        method_name : str
            Name of the RPC method.

        Returns
        -------
        MethodInfo
            Metadata about the method.

        Raises
        ------
        KeyError
            If method is not registered.

        Examples
        --------
        >>> info = MyConsumer.get_method_info('get_user')
        >>> print(info.signature)
        (user_id: int) -> dict
        >>> print(info.docstring)
        Get user information by ID.
        """
        registry = get_registry()

        # Check methods first, then notifications
        methods = registry.get_methods(cls)
        is_notification = False
        if method_name in methods:
            wrapper = methods[method_name]
        else:
            notifications = registry.get_notifications(cls)
            if method_name in notifications:
                wrapper = notifications[method_name]
                is_notification = True
            else:
                msg = f"Method '{method_name}' not registered"
                raise KeyError(msg)

        # Extract metadata
        func = wrapper.func if isinstance(wrapper, RpcMethodWrapper) else wrapper
        sig = inspect.signature(func)

        return MethodInfo(
            name=method_name,
            func=func,
            signature=str(sig),
            docstring=func.__doc__,
            accepts_context=(
                wrapper.accepts_context
                if isinstance(wrapper, RpcMethodWrapper)
                else False
            ),
            transport_options=(
                wrapper.options if isinstance(wrapper, RpcMethodWrapper) else {}
            ),
            is_notification=is_notification,
        )

    @classmethod
    def describe_api(cls) -> dict[str, Any]:
        """Generate a JSON-serializable API description.

        Returns
        -------
        dict[str, Any]
            API description including all methods and notifications.

        Examples
        --------
        >>> api_desc = MyConsumer.describe_api()
        >>> print(json.dumps(api_desc, indent=2))
        {
          "methods": [
            {
              "name": "get_user",
              "signature": "(user_id: int) -> dict",
              "doc": "Get user information",
              "accepts_context": true
            }
          ],
          "notifications": [...]
        }
        """
        methods_list = []
        for method_name in cls.get_rpc_methods():
            try:
                info = cls.get_method_info(method_name)
                methods_list.append(
                    {
                        "name": info.name,
                        "signature": info.signature,
                        "doc": info.docstring,
                        "accepts_context": info.accepts_context,
                        "transports": [
                            k for k, v in info.transport_options.items() if v
                        ],
                    }
                )
            except Exception as e:
                logger.warning("Failed to introspect method %s: %s", method_name, e)

        notifications_list = []
        for notif_name in cls.get_rpc_notifications():
            try:
                info = cls.get_method_info(notif_name)
                notifications_list.append(
                    {
                        "name": info.name,
                        "signature": info.signature,
                        "doc": info.docstring,
                        "accepts_context": info.accepts_context,
                    }
                )
            except Exception as e:
                logger.warning(
                    "Failed to introspect notification %s: %s", notif_name, e
                )

        return {
            "jsonrpc": "2.0",
            "consumer": cls.__name__,
            "methods": methods_list,
            "notifications": notifications_list,
        }

    def validate_scope(self) -> None:
        """Validate and sanitize scope data.
        Ensures scope contains required fields and has expected types.
        Should be called during connection establishment.

        The scope dict is provided by Django Channels and contains connection
        metadata such as client information, headers, and connection type.
        This method validates that the scope conforms to expected structure.

        Raises
        ------
        ValueError
            If scope is invalid or missing required fields.

        Examples
        --------
        Validate scope during connection establishment::

            class SecureConsumer(JsonRpcWebsocketConsumer):
                def connect(self):
                    try:
                        self.validate_scope()
                        # Extract and validate client IP
                        client_host, client_port = self.scope["client"]
                        if not self.is_allowed_ip(client_host):
                            self.close()
                            return
                        self.accept()
                    except ValueError as e:
                        logger.error(f"Invalid scope: {e}")
                        self.close()

        Use scope data for authentication::

            class AuthenticatedConsumer(JsonRpcWebsocketConsumer):
                def connect(self):
                    self.validate_scope()
                    # Access validated scope data
                    headers = dict(self.scope.get("headers", []))
                    auth_token = headers.get(b"authorization", b"").decode()
                    if not self.verify_token(auth_token):
                        self.close()
                    else:
                        self.accept()
        """
        if not isinstance(self.scope, dict):
            error_msg = "Scope must be a dict"
            raise ValueError(error_msg)

        # Validate type
        scope_type = self.scope.get("type")
        if scope_type not in ("websocket", "websocket.receive", "websocket.disconnect"):
            logger.warning("Unexpected scope type: %s", scope_type)

        # Validate client if present
        if "client" in self.scope:
            client = self.scope["client"]
            # Client tuple should be (host, port)
            if not isinstance(client, list | tuple) or len(client) != 2:
                logger.warning("Malformed client in scope: %s", client)

    def notify_channel(self, method: str, params: dict[str, Any]) -> None:
        """Notify a channel.
        Sends a JSON-RPC 2.0 notification (a request without an id) to the connected
        client. Unlike regular RPC method calls, notifications do not expect or wait
        for a response.

        Parameters
        ----------
        method : str
            Method name.
        params : dict[str, Any]
            Method parameters.

        Examples
        --------
        Send a notification to update client state::

            class MyConsumer(JsonRpcWebsocketConsumer):
                def on_data_changed(self, new_data):
                    # Notify client about data change without expecting response
                    self.notify_channel(
                        method="data_updated",
                        params={"timestamp": time.time(), "data": new_data}
                    )

        Send a notification to trigger client action::

            class MonitoringConsumer(JsonRpcWebsocketConsumer):
                @JsonRpcWebsocketConsumer.rpc_method()
                def start_monitoring(self, interval: int):
                    # Client requested monitoring, send periodic notifications
                    while self.monitoring_active:
                        metrics = self.collect_metrics()
                        self.notify_channel(
                            method="metrics_update",
                            params={"metrics": metrics}
                        )
                        time.sleep(interval)
                    return {"status": "monitoring_started"}
        """
        # Create a JSON-RPC 2.0 notification (request without id)
        content = create_json_rpc_request(rpc_id=None, method=method, params=params)
        self.send(self.encode_json(content))

    def _validate_call(self, data: dict[str, Any]) -> None:
        """Validate RPC call data.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.

        Raises
        ------
        JsonRpcError
            Invalid call data.
        """
        logger.debug("Validating call data: %s", data)

        # First, try to extract and validate ID (used in all error responses)
        if "id" in data:
            rpc_id = data["id"]
            # Validate ID type per JSON-RPC 2.0 spec
            if rpc_id is not None and not isinstance(rpc_id, str | int | float):
                id_type = type(rpc_id).__name__
                raise JsonRpcError(
                    None,  # Invalid ID, so don't use it in error
                    JsonRpcErrorCode.INVALID_REQUEST,
                    data={
                        "field": "id",
                        "error": f"must be string, number, or null, got {id_type}",
                    },
                )
        else:
            rpc_id = None

        # Validate JSON-RPC version
        bad_json_rpc_version = data.get("jsonrpc") != "2.0"
        if bad_json_rpc_version:
            logger.warning(logs.INVALID_JSON_RPC_VERSION, data.get("jsonrpc"))
            raise JsonRpcError(
                rpc_id,  # Use validated ID (or None if not present)
                JsonRpcErrorCode.INVALID_REQUEST,
                data={"version": data.get("jsonrpc")},
            )

        # Validate method field
        no_method = "method" not in data
        bad_method = not isinstance(data.get("method"), str)

        if no_method:
            raise JsonRpcError(
                rpc_id,
                JsonRpcErrorCode.INVALID_REQUEST,
                data={"field": "Missing required 'method' field"},
            )

        if bad_method:
            method_type = type(data.get("method")).__name__
            raise JsonRpcError(
                rpc_id,
                JsonRpcErrorCode.INVALID_REQUEST,
                data={"field": f"'method' must be a string, got {method_type}"},
            )

        # Check size limits
        check_size_limits(data, rpc_id)

        logger.debug("Call data is valid")

    def _get_method(self, data: dict[str, Any], *, is_notification: bool) -> Callable:
        """Get the method to call.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.
        is_notification : bool
            Whether the call is a notification.

        Returns
        -------
        Callable
            Method to call.

        Raises
        ------
        JsonRpcError
            Invalid call data provided.
        JsonRpcError
            RPC method not supported.
        """
        self._validate_call(data)
        rpc_id = data.get("id")
        method_name = data["method"]
        logger.debug("Getting method: %s", method_name)

        registry = get_registry()
        methods = (
            registry.get_notifications(self.__class__)
            if is_notification
            else registry.get_methods(self.__class__)
        )

        try:
            method = methods[method_name]
        except KeyError as e:
            raise JsonRpcError(
                rpc_id, JsonRpcErrorCode.METHOD_NOT_FOUND, data={"method": method_name}
            ) from e
        protocol = self.scope["type"]
        # Handle both RpcMethodWrapper and raw Callable (backward compatibility)
        if isinstance(method, RpcMethodWrapper):
            # Check if method is enabled for this protocol
            # Default to True for unknown protocols for backward compatibility
            if not method.options.get(protocol, True):
                raise JsonRpcError(rpc_id, JsonRpcErrorCode.METHOD_NOT_FOUND)
            logger.debug("Method found: %s", method.func.__name__)
        else:
            # Legacy raw callable with options attribute
            if not getattr(method, "options", {}).get(protocol, True):
                raise JsonRpcError(rpc_id, JsonRpcErrorCode.METHOD_NOT_FOUND)
            logger.debug("Method found: %s", method.__name__)
        return method

    def _get_params(self, data: dict[str, Any]) -> dict | list:
        """Get RPC call parameters from request data.

        Parameters
        ----------
        data : dict[str, Any]
            Request data.

        Returns
        -------
        dict | list
            Parameters, or empty dict if not provided.

        Raises
        ------
        JsonRpcError
            Invalid call data provided.
        """
        logger.debug("Getting call parameters: %s", data)

        # Check for params first (standard), then arguments (deprecated)
        if "params" in data:
            params = data["params"]
        elif "arguments" in data:
            params = data["arguments"]
        else:
            params = {}

        # None is treated as empty dict
        if params is None:
            return {}

        # Validate type
        if not isinstance(params, list | dict):
            rpc_id = data.get("id")
            raise JsonRpcError(
                rpc_id,
                JsonRpcErrorCode.INVALID_PARAMS,
                data={
                    "expected": "dict or list",
                    "actual": type(params).__name__,
                },
            )

        logger.debug("Call parameters found: %s", params)
        return params

    def _get_rpc_id(self, data: dict[str, Any]) -> tuple[str | None, str]:
        """Get the RPC ID.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.

        Returns
        -------
        tuple[str | None, str]
            RPC ID and RPC ID key (always "id" per JSON-RPC 2.0 spec).
        """
        logger.debug("Extracting RPC ID: %s", data)
        rpc_id = data.get("id")
        if rpc_id is not None:
            logger.debug("RPC ID found: %s", rpc_id)
        return rpc_id, "id"

    def _process_call(
        self, data: dict[str, Any], *, is_notification: bool = False
    ) -> dict[str, Any] | None:
        """Process the received remote procedure call data.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.
        is_notification : bool, optional
            Whether the call is a notification, by default False.

        Returns
        -------
        dict[str, Any] | None
            Result of the remote procedure call.
        """
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
        result = self._execute_called_method(method, params, context)
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

    def _apply_request_middleware(
        self,
        data: dict[str, Any],
        rpc_id: str | int | float | None,
        method_name: str,
        start_time: float,
        is_notification: bool,  # noqa: ARG002, FBT001
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
                        str(e)[:200],
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

    def _apply_response_middleware(
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
                    result = mw.process_response(result, self)
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
            from channels_rpc.config import get_config  # noqa: PLC0415

            config = get_config()

            if config.sanitize_errors:
                # Production mode: Log without stack trace
                logger.error(
                    "Unexpected error processing RPC call '%s': %s",
                    method_name,
                    f"{type(exception).__name__}: {str(exception)[:200]}",
                )
            else:
                # Development mode: Log with full stack trace
                logger.exception("Unexpected error processing RPC call")

            return generate_error_response(
                rpc_id=rpc_id,
                code=JsonRpcErrorCode.INTERNAL_ERROR,
                message="Internal server error",
                data=None,  # Never leak internal details
            )

    def _intercept_call(self, data: dict[str, Any]) -> tuple[Any, bool]:
        """Handle JSON-RPC 2.0 requests and responses.

        Parameters
        ----------
        data : dict[str, Any]
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
        processed_data, error = self._apply_request_middleware(
            data, rpc_id, method_name, start_time, is_notification
        )
        if error is not None:
            return error, is_notification

        # Type narrowing: If error is None, processed_data must be valid
        # Note: Using explicit checks instead of assert for production safety
        # (asserts are removed with -O optimization flag)
        if processed_data is None:
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

        data = processed_data  # Now data is guaranteed to be non-None

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
            result = self._process_call(data, is_notification=is_notification)

            # Apply response middleware (reverse order, non-notifications only)
            result = self._apply_response_middleware(result, is_notification)

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

    def _execute_called_method(
        self,
        method: Callable | RpcMethodWrapper,
        params: list | dict,
        context: RpcContext,
    ) -> Any:
        """Execute RPC method with appropriate parameter unpacking.

        Uses cached introspection result for optimal performance.

        Parameters
        ----------
        method : Callable | RpcMethodWrapper
            Method to execute.
        params : list | dict
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
            # Check if it's an old-style method wrapper with accepts_consumer
            actual_method = method
            accepts_context = False

        # Execute with appropriate calling convention
        if accepts_context:
            if isinstance(params, list):
                return actual_method(context, *params)
            else:
                return actual_method(context, **params)
        elif isinstance(params, list):
            return actual_method(*params)
        else:
            return actual_method(**params)

    def _base_receive_json(self, data: dict[str, Any]) -> None:
        """Called when receiving a message.

        Parameters
        ----------
        data : dict[str, Any]
            Received message data.
        """
        logger.debug("Received JSON message: %s", data)
        result, is_notification = self._intercept_call(data)
        if not is_notification:
            logger.debug("Sending result: %s", result)
            self.send_json(result)
