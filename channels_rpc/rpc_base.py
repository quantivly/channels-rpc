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
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass
from inspect import getfullargspec
from typing import TYPE_CHECKING, Any

from channels_rpc import logs
from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    RPC_ERRORS,
    JsonRpcError,
    generate_error_response,
)
from channels_rpc.utils import (
    create_json_rpc_request,
    create_json_rpc_response,
)

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
    """

    func: Callable[..., Any]
    options: dict[str, bool]
    name: str

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

    rpc_methods: defaultdict = defaultdict(dict)
    rpc_notifications: defaultdict = defaultdict(dict)

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
        import warnings  # noqa: PLC0415

        if not http:
            warnings.warn(
                "The 'http' parameter is deprecated and ignored. "
                "HTTP transport was removed in version 1.0.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        def wrap(method: Callable) -> RpcMethodWrapper:
            name = method_name or method.__name__
            wrapper = RpcMethodWrapper(
                func=method,
                options={"websocket": websocket, "http": http},
                name=name,
            )
            cls.rpc_methods[id(cls)][name] = wrapper
            return wrapper

        return wrap

    @classmethod
    def get_rpc_methods(cls) -> list[str]:
        """List RPC methods available for this consumer.

        Returns
        -------
        list[str]
            List of RPC methods available for this consumer.
        """
        try:
            return list(cls.rpc_methods[id(cls)])
        except KeyError:
            return []

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
        import warnings  # noqa: PLC0415

        if not http:
            warnings.warn(
                "The 'http' parameter is deprecated and ignored. "
                "HTTP transport was removed in version 1.0.0.",
                DeprecationWarning,
                stacklevel=2,
            )

        def wrap(method: Callable) -> RpcMethodWrapper:
            name = notification_name or method.__name__
            wrapper = RpcMethodWrapper(
                func=method,
                options={"websocket": websocket, "http": http},
                name=name,
            )
            cls.rpc_notifications[id(cls)][name] = wrapper
            return wrapper

        return wrap

    @classmethod
    def get_rpc_notifications(cls) -> list[str]:
        """List RPC notifications available for this consumer.

        Returns
        -------
        list[str]
            List of RPC notifications available for this consumer.
        """
        try:
            return list(cls.rpc_notifications[id(cls)])
        except KeyError:
            return []

    def validate_scope(self) -> None:
        """Validate and sanitize scope data.

        Ensures scope contains required fields and has expected types.
        Should be called during connection establishment.

        Raises
        ------
        ValueError
            If scope is invalid or missing required fields.
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

        Parameters
        ----------
        method : str
            Method name.
        params : dict[str, Any]
            Method parameters.
        """
        # Create a JSON-RPC 2.0 notification (request without id)
        content = create_json_rpc_request(rpc_id=None, method=method, params=params)
        self.send(self.encode_json(content))

    def validate_call(self, data: dict[str, Any]) -> None:
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
                rpc_id, INVALID_REQUEST, data={"version": data.get("jsonrpc")}
            )

        if no_method:
            raise JsonRpcError(
                rpc_id,
                INVALID_REQUEST,
                data={"field": "Missing required 'method' field"},
            )

        if bad_method:
            method_type = type(data.get("method")).__name__
            raise JsonRpcError(
                rpc_id,
                INVALID_REQUEST,
                data={"field": f"'method' must be a string, got {method_type}"},
            )

        # Check size limits
        from channels_rpc.limits import check_size_limits  # noqa: PLC0415

        check_size_limits(data, rpc_id)

        logger.debug("Call data is valid")

    def get_method(self, data: dict[str, Any], *, is_notification: bool) -> Callable:
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
        self.validate_call(data)
        rpc_id = data.get("id")
        method_name = data["method"]
        logger.debug("Getting method: %s", method_name)
        class_id = id(self.__class__)
        methods = self.rpc_notifications if is_notification else self.rpc_methods
        try:
            method = methods[class_id][method_name]
        except KeyError as e:
            raise JsonRpcError(
                rpc_id, METHOD_NOT_FOUND, data={"method": method_name}
            ) from e
        protocol = self.scope["type"]
        # Handle both RpcMethodWrapper and raw Callable (backward compatibility)
        if isinstance(method, RpcMethodWrapper):
            if not method.options[protocol]:
                raise JsonRpcError(rpc_id, METHOD_NOT_FOUND)
            logger.debug("Method found: %s", method.func.__name__)
        else:
            # Legacy raw callable with options attribute
            if not getattr(method, "options", {}).get(protocol, True):
                raise JsonRpcError(rpc_id, METHOD_NOT_FOUND)
            logger.debug("Method found: %s", method.__name__)
        return method

    def get_params(self, data: dict[str, Any]) -> dict | list:
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
                INVALID_PARAMS,
                data={
                    "expected": "dict or list",
                    "actual": type(params).__name__,
                },
            )

        logger.debug("Call parameters found: %s", params)
        return params

    def get_rpc_id(self, data: dict[str, Any]) -> tuple[str | None, str]:
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

    def process_call(
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
        method = self.get_method(data, is_notification=is_notification)
        params = self.get_params(data)
        rpc_id, _ = self.get_rpc_id(data)
        logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")
        result = self.execute_called_method(method, params)
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
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None
        return result

    def intercept_call(self, data: dict[str, Any]) -> tuple[Any, bool]:
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

        if not data:
            logger.warning(logs.EMPTY_CALL)
            message = RPC_ERRORS[INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=INVALID_REQUEST, message=message
            )
            return result, False

        if not isinstance(data, dict):
            logger.warning(f"Invalid message type: {type(data).__name__}")
            message = RPC_ERRORS[INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=INVALID_REQUEST, message=message
            )
            return result, False

        # Check if this is a JSON-RPC 2.0 response
        if "result" in data or "error" in data:
            logger.debug(f"Received JSON-RPC 2.0 response: {data}")
            return data, True

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
            result = self.process_call(data, is_notification=is_notification)
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

    def execute_called_method(
        self, method: Callable | RpcMethodWrapper, params: list | dict
    ) -> Any:
        """Execute RPC method with appropriate parameter unpacking.

        Parameters
        ----------
        method : Callable | RpcMethodWrapper
            Method to execute.
        params : list | dict
            Parameters to pass.

        Returns
        -------
        Any
            Result from the method.
        """
        # Unwrap RpcMethodWrapper if needed
        if hasattr(method, "func"):
            actual_method = method.func
        else:
            actual_method = method

        # Check if method accepts **kwargs (can inject consumer)
        spec = getfullargspec(actual_method)
        accepts_consumer = spec.varkw is not None  # Has **kwargs parameter

        # Execute with appropriate calling convention
        if isinstance(params, list):
            if accepts_consumer:
                return actual_method(*params, consumer=self)
            else:
                return actual_method(*params)
        elif accepts_consumer:
            return actual_method(**params, consumer=self)
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
        result, is_notification = self.intercept_call(data)
        if not is_notification:
            logger.debug("Sending result: %s", result)
            self.send_json(result)
