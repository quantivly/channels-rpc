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

import json
import logging
from collections import defaultdict
from collections.abc import Callable
from inspect import getfullargspec
from typing import Any

from six import string_types

from channels_rpc import logs
from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    RPC_ERRORS,
    JsonRpcError,
    generate_error_response,
)
from channels_rpc.utils import create_json_rpc_frame

logger = logging.getLogger("django.channels.rpc")


class RpcBase:
    """Base class for RPC consumers.

    Variant of WebsocketConsumer that automatically JSON-encodes and decodes
    messages as they come in and go out. Expects everything to be text; will
    error on binary data.

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

    RPC_ERROR_TO_HTTP_CODE: dict[int, int] = {
        PARSE_ERROR: 500,
        INVALID_REQUEST: 400,
        METHOD_NOT_FOUND: 404,
        INVALID_PARAMS: 500,
        INTERNAL_ERROR: 500,
        GENERIC_APPLICATION_ERROR: 500,
    }
    RPC_ID_KEYS: list[str] = ["id", "call_id"]

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
            Whether HTTP transport can use this function, by default True.

        Returns
        -------
        Callable
            Decorated function.
        """

        def wrap(method: Callable) -> Callable:
            name = method_name or method.__name__
            method.options = {"websocket": websocket, "http": http}
            cls.rpc_methods[id(cls)][name] = method
            return method

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
            Whether HTTP transport can use this function, by default True.

        Returns
        -------
        Callable
            Decorated function.
        """

        def wrap(method: Callable) -> Callable:
            name = notification_name or method.__name__
            method.options = {"websocket": websocket, "http": http}
            cls.rpc_notifications[id(cls)][name] = method
            return method

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

    def notify_channel(self, method: str, params: dict[str, Any]) -> None:
        """Notify a channel.

        Parameters
        ----------
        method : str
            Method name.
        params : dict[str, Any]
            Method parameters.
        """
        content = create_json_rpc_frame(method=method, params=params)
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
        bad_method = not isinstance(data.get("method"), string_types)
        if bad_json_rpc_version:
            logger.warning(logs.INVALID_JSON_RPC_VERSION, data.get("jsonrpc"))
        if no_method or bad_method:
            raise JsonRpcError(rpc_id, INVALID_REQUEST)
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
        rpc_id = data.get("id") or data.get("call_id")
        method_name = data["method"]
        logger.debug("Getting method: %s", method_name)
        class_id = id(self.__class__)
        methods = self.rpc_notifications if is_notification else self.rpc_methods
        try:
            method = methods[class_id][method_name]
        except KeyError as e:
            raise JsonRpcError(rpc_id, METHOD_NOT_FOUND) from e
        protocol = self.scope["type"]
        if not method.options[protocol]:
            raise JsonRpcError(rpc_id, METHOD_NOT_FOUND)
        logger.debug("Method found: %s", method.__name__)
        return method

    def get_params(self, data: dict[str, Any]) -> dict | list:
        """Get the parameters to pass to the method.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.

        Returns
        -------
        dict | list
            Parameters to pass to the method.

        Raises
        ------
        JsonRpcError
            Invalid call data provided.
        """
        logger.debug("Getting call parameters: %s", data)
        params = data.get("params") or data.get("arguments") or {}
        if not isinstance(params, (list, dict)):
            rpc_id = data.get("id")
            raise JsonRpcError(rpc_id, INVALID_PARAMS)
        logger.debug("Call parameters found: %s", params)
        return params

    def get_rpc_id(self, data: dict[str, Any]) -> tuple[str | None, str | None]:
        """Get the RPC ID.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.

        Returns
        -------
        tuple[str | None, str | None]
            RPC ID and RPC ID key.
        """
        logger.debug("Extracting RPC ID: %s", data)
        for rpc_id_key in self.RPC_ID_KEYS:
            if rpc_id_key in data:
                logger.debug(
                    "RPC ID with key '%s' found: %s", rpc_id_key, data[rpc_id_key]
                )
                return data[rpc_id_key], rpc_id_key

    def process_call(
        self, data: dict[str, Any], *, is_notification: bool = False
    ) -> dict | None:
        """Process the received remote procedure call data.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.
        is_notification : bool, optional
            Whether the call is a notification, by default False.

        Returns
        -------
        dict | None
            Result of the remote procedure call.
        """
        method = self.get_method(data, is_notification=is_notification)
        params = self.get_params(data)
        rpc_id, rpc_id_key = self.get_rpc_id(data)
        logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")
        result = self.execute_called_method(method, params)
        if not is_notification:
            logger.debug("Execution result: %s", result)
            result = create_json_rpc_frame(
                result=result,
                rpc_id=rpc_id,
                rpc_id_key=rpc_id_key,
                method=data["method"],
                params=params,
                compressed=False,
            )
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None
        return result

    def intercept_call(self, data: dict[str, Any]) -> tuple[Any, bool]:
        """Handles calls and notifications.

        Parameters
        ----------
        data : dict[str, Any]
            Received message data.

        Returns
        -------
        tuple[Any, bool]
            Result of the remote procedure call and whether it is a notification.
        """
        logger.debug("Intercepting call: %s", data)
        if not data:
            logger.warning(logs.EMPTY_CALL)
            message = RPC_ERRORS[INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=INVALID_REQUEST, message=message
            )
            return result, False
        response = None
        if isinstance(data, dict) and "response" in data:
            response = data["response"]
            if response is not None:
                logger.debug(f"Received RPC response: {response}")
                return response, True
        if isinstance(data, dict) and "request" in data:
            request = data["request"]
            if request is not None:
                logger.debug(f"Received RPC request: {request}")
        result = None
        is_notification: bool = None
        rpc_id = request.get("id") or request.get("call_id")
        method_name = request.get("method")
        logger.debug(logs.CALL_INTERCEPTED, request)
        if isinstance(request, dict):
            is_notification = method_name is not None and rpc_id is None
            if rpc_id:
                logger.info(logs.RPC_METHOD_CALL_START, method_name, rpc_id)
            else:
                logger.info(logs.RPC_NOTIFICATION_START, method_name)
            try:
                result = self.process_call(request, is_notification=is_notification)
            except JsonRpcError as e:
                result = e.as_dict()
            except Exception as e:
                logger.debug("Application error: %s", e)
                exception_data = e.args[0] if len(e.args) == 1 else e.args
                result = generate_error_response(
                    rpc_id=rpc_id,
                    code=GENERIC_APPLICATION_ERROR,
                    message=str(e),
                    data=exception_data,
                )
        # elif isinstance(data, list):
        #     # TODO: implement batch calls
        #     invalid_call_data = [x for x in data if not isinstance(x, dict)]
        #     if invalid_call_data:
        #         message = RPC_ERRORS[INVALID_REQUEST]
        #         result = generate_error_response(
        #             rpc_id=None, code=INVALID_REQUEST, message=message
        #         )
        if rpc_id:
            logger.debug(logs.RPC_METHOD_CALL_END, rpc_id, method_name, result)
        else:
            logger.debug(logs.RPC_NOTIFICATION_END, method_name)
        return result, is_notification

    def execute_called_method(self, method: Callable, params: list | dict) -> Any:
        """Get the result of the remote procedure call.

        Parameters
        ----------
        method : Callable
            Method to call.
        params : list | dict
            Parameters to pass to the method.

        Returns
        -------
        Any
            Result of the remote procedure call.
        """
        func_args = getfullargspec(method).varkw
        if func_args and "kwargs" in func_args:
            return (
                method(*params, consumer=self)
                if isinstance(params, list)
                else method(**params, consumer=self)
            )
        elif isinstance(params, list):
            return method(*params)
        else:
            return method(**params)

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
