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

import functools
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from channels_rpc import logs
from channels_rpc.exceptions import (
    JsonRpcError,
    JsonRpcErrorCode,
    generate_error_response,
)
from channels_rpc.utils import create_json_rpc_request, create_json_rpc_response

if TYPE_CHECKING:
    from channels_rpc.context import RpcContext

logger = logging.getLogger("django.channels.rpc")


@dataclass
class RpcMethodWrapper:
    """Wrapper for RPC method with transport options.

    Attributes
    ----------
    func : Callable
        The actual RPC method function.
    options : dict[str, bool]
        Transport options (websocket, http).
    name : str
        Method name to register.
    accepts_context : bool
        Whether method accepts RpcContext as first parameter.
    """

    func: Callable[..., Any]
    options: dict[str, bool]
    name: str
    accepts_context: bool

    def __post_init__(self) -> None:
        """Initialize wrapper attributes after dataclass init."""
        # Set __name__ and __qualname__ to mimic the wrapped function
        object.__setattr__(self, "__name__", getattr(self.func, "__name__", self.name))
        object.__setattr__(
            self, "__qualname__", getattr(self.func, "__qualname__", self.name)
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make the wrapper callable."""
        return self.func(*args, **kwargs)

    def __get__(self, obj: Any, objtype: Any = None) -> Callable[..., Any]:
        """Support instance method binding."""
        if obj is None:
            return self
        return functools.partial(self.__call__, obj)


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

    References
    ----------
    - http://groups.google.com/group/json-rpc/web/json-rpc-2-0
    """

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
        http: bool = True,
    ) -> Callable:
        """A decorator for registering RPC methods.

        Parameters
        ----------
        method_name : str, optional
            RPC method name for the function, by default None.
        websocket : bool, optional
            Whether WebSocket transport can use this function, by default True.
        http : bool, optional
            DEPRECATED: HTTP transport removed in 1.0.0. Parameter ignored.

        Returns
        -------
        Callable
            Decorated function.
        """
        import inspect  # noqa: PLC0415
        import warnings  # noqa: PLC0415

        if not http:
            warnings.warn(
                "The 'http' parameter is deprecated and ignored. "
                "HTTP transport was removed in version 1.0.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        def wrap(method: Callable) -> RpcMethodWrapper:
            from channels_rpc.context import RpcContext  # noqa: PLC0415
            from channels_rpc.registry import get_registry  # noqa: PLC0415

            name = method_name or method.__name__

            # Check if first parameter is RpcContext
            accepts_context = False
            try:
                sig = inspect.signature(method)
                params = list(sig.parameters.values())
                # Skip 'self' parameter if present (for methods vs free functions)
                first_param_idx = 1 if (params and params[0].name == "self") else 0
                if len(params) > first_param_idx:
                    first_param = params[first_param_idx]
                    if first_param.annotation is not inspect.Parameter.empty:
                        # Check if annotation is RpcContext
                        # (handles both direct type and string annotation
                        # from __future__.annotations)
                        annotation = first_param.annotation
                        if (
                            annotation is RpcContext
                            or annotation == "RpcContext"
                            or getattr(annotation, "__name__", "") == "RpcContext"
                        ):
                            accepts_context = True
            except Exception:  # noqa: S110
                # If inspection fails, assume no context
                pass

            wrapper = RpcMethodWrapper(
                func=method,
                options={"websocket": websocket, "http": http},
                name=name,
                accepts_context=accepts_context,
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
        from channels_rpc.registry import get_registry  # noqa: PLC0415

        registry = get_registry()
        return registry.list_method_names(cls)

    @classmethod
    def rpc_notification(
        cls,
        notification_name: str | None = None,
        *,
        websocket: bool = True,
        http: bool = True,
    ) -> Callable:
        """A decorator for registering RPC notifications.

        Parameters
        ----------
        notification_name : str, optional
            RPC name for the function, by default None.
        websocket : bool, optional
            Whether WebSocket transport can use this function, by default True.
        http : bool, optional
            DEPRECATED: HTTP transport removed in 1.0.0. Parameter ignored.

        Returns
        -------
        Callable
            Decorated function.
        """
        import inspect  # noqa: PLC0415
        import warnings  # noqa: PLC0415

        if not http:
            warnings.warn(
                "The 'http' parameter is deprecated and ignored. "
                "HTTP transport was removed in version 1.0.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        def wrap(method: Callable) -> RpcMethodWrapper:
            from channels_rpc.context import RpcContext  # noqa: PLC0415
            from channels_rpc.registry import get_registry  # noqa: PLC0415

            name = notification_name or method.__name__

            # Check if first parameter is RpcContext
            accepts_context = False
            try:
                sig = inspect.signature(method)
                params = list(sig.parameters.values())
                # Skip 'self' parameter if present (for methods vs free functions)
                first_param_idx = 1 if (params and params[0].name == "self") else 0
                if len(params) > first_param_idx:
                    first_param = params[first_param_idx]
                    if first_param.annotation is not inspect.Parameter.empty:
                        # Check if annotation is RpcContext
                        # (handles both direct type and string annotation
                        # from __future__.annotations)
                        annotation = first_param.annotation
                        if (
                            annotation is RpcContext
                            or annotation == "RpcContext"
                            or getattr(annotation, "__name__", "") == "RpcContext"
                        ):
                            accepts_context = True
            except Exception:  # noqa: S110
                # If inspection fails, assume no context
                pass

            wrapper = RpcMethodWrapper(
                func=method,
                options={"websocket": websocket, "http": http},
                name=name,
                accepts_context=accepts_context,
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
        from channels_rpc.registry import get_registry  # noqa: PLC0415

        registry = get_registry()
        return list(registry.get_notifications(cls).keys())

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
            if not isinstance(client, (list, tuple)) or len(client) != 2:
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
        rpc_id = data.get("id")
        bad_json_rpc_version = data.get("jsonrpc") != "2.0"
        no_method = "method" not in data
        bad_method = not isinstance(data.get("method"), str)

        # JSON-RPC 2.0 requires exact version match
        if bad_json_rpc_version:
            logger.warning(logs.INVALID_JSON_RPC_VERSION, data.get("jsonrpc"))
            raise JsonRpcError(
                rpc_id,
                JsonRpcErrorCode.INVALID_REQUEST,
                data={"version": data.get("jsonrpc")},
            )

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
        from channels_rpc.limits import check_size_limits  # noqa: PLC0415

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
        from channels_rpc.registry import get_registry  # noqa: PLC0415

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
            if not method.options[protocol]:
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
        if not isinstance(params, (list, dict)):
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
        from channels_rpc.validation import validate_rpc_data  # noqa: PLC0415

        logger.debug("Intercepting call: %s", data)

        result: dict[str, Any] | None

        # Use shared validation logic
        error, is_response = validate_rpc_data(data)
        if error or is_response:
            return error or data, is_response

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
            result = self._process_call(data, is_notification=is_notification)
        except JsonRpcError as e:
            # Re-raise JSON-RPC errors as-is
            result = e.as_dict()
        except (ValueError, TypeError, KeyError, AttributeError, RuntimeError) as e:
            # Expected application-level errors
            logger.info("Application error in RPC method: %s", e)
            result = generate_error_response(
                rpc_id=rpc_id,
                code=JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
                message="Application error occurred",
                data=None,  # Never leak internal details
            )
        except Exception:
            # Unexpected errors - these indicate bugs
            logger.exception("Unexpected error processing RPC call")
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
