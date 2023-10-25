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

from django.conf import settings
from six import string_types

from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    RPC_ERRORS,
    JsonRpcError,
    MethodNotSupportedError,
    generate_error_response,
)
from channels_rpc.utils import create_json_rpc_frame

logger = logging.getLogger(__name__)


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

    available_rpc_methods: defaultdict = defaultdict(dict)
    available_rpc_notifications: defaultdict = defaultdict(dict)

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

        def wrap(f: Callable) -> Callable:
            name = method_name if method_name is not None else f.__name__
            f.options = dict(websocket=websocket, http=http)
            cls.available_rpc_methods[id(cls)][name] = f
            return f

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
            return list(cls.available_rpc_methods[id(cls)].keys())
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

        def wrap(f):
            name = notification_name if notification_name is not None else f.__name__
            f.options = dict(websocket=websocket, http=http)
            cls.available_rpc_notifications[id(cls)][name] = f
            return f

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
            return list(cls.available_rpc_notifications[id(cls)].keys())
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
        rpc_id = data.get("id")
        if data.get("jsonrpc") != "2.0":
            raise JsonRpcError(rpc_id, self.INVALID_REQUEST)

        try:
            method_name = data["method"]
        except KeyError as e:
            raise JsonRpcError(rpc_id, self.INVALID_REQUEST) from e

        if not isinstance(method_name, string_types):
            raise JsonRpcError(rpc_id, self.INVALID_REQUEST)

        if method_name.startswith("_"):
            raise JsonRpcError(rpc_id, self.METHOD_NOT_FOUND)

        try:
            class_id = id(self.__class__)
            if is_notification:
                method = self.__class__.available_rpc_notifications[class_id][
                    method_name
                ]
            else:
                method = self.__class__.available_rpc_methods[class_id][method_name]
            proto = self.scope["type"]
            if not method.options[proto]:
                msg = f"Method not available through {proto}"
                raise MethodNotSupportedError(msg)
        except (KeyError, MethodNotSupportedError) as e:
            raise JsonRpcError(rpc_id, self.METHOD_NOT_FOUND) from e
        return method

    def _get_params(self, data: dict[str, Any]) -> dict | list:
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
        params = data.get("params", [])
        if not isinstance(params, (list, dict)):
            rpc_id = data.get("id")
            raise JsonRpcError(rpc_id, self.INVALID_PARAMS)
        return params

    def __process(
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
        method = self._get_method(data, is_notification=is_notification)
        params = self._get_params(data)
        if settings.DEBUG:
            logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")
        result = self.__get_result(method, params)
        # check and pack result
        if not is_notification:
            if settings.DEBUG:
                logger.debug("Execution result: %s", result)
            result = create_json_rpc_frame(result=result, rpc_id=data.get("id"))
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None
        return result

    def _handle(self, data: dict[str, Any]):
        """
        Handle
        :param data:
        :return:
        """
        result = None
        is_notification = False

        if data is None:
            message = RPC_ERRORS[self.INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=self.INVALID_REQUEST, message=message
            )

        elif isinstance(data, dict):
            method_name = data.get("method")
            rpc_id = data.get("id")
            try:
                is_notification = method_name is not None and rpc_id is None
                result = self.__process(data, is_notification=is_notification)
            except JsonRpcError as e:
                result = e.as_dict()
            except Exception as e:
                logger.debug("Application error: %s", e)
                exception_data = e.args[0] if len(e.args) == 1 else e.args
                result = generate_error_response(
                    rpc_id=data.get("id"),
                    code=GENERIC_APPLICATION_ERROR,
                    message=str(e),
                    data=exception_data,
                )
        elif isinstance(data, list):
            # TODO: implement batch calls
            invalid_call_data = [x for x in data if not isinstance(x, dict)]
            if invalid_call_data:
                message = RPC_ERRORS[self.INVALID_REQUEST]
                result = generate_error_response(
                    rpc_id=None, code=self.INVALID_REQUEST, message=message
                )
        return result, is_notification

    def __get_result(self, method: Callable, params: list | dict) -> Any:
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
        result, is_notification = self._handle(data)

        # Send response back only if it is a call, not notification
        if not is_notification:
            self.send_json(result)
