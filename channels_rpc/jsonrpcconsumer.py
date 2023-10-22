import json
import logging
from inspect import getfullargspec

from channels.generic.http import AsyncHttpConsumer
from channels.generic.websocket import AsyncJsonWebsocketConsumer, JsonWebsocketConsumer
from django.conf import settings
from six import string_types

# Get an instance of a logger
logger = logging.getLogger(__name__)

keywords_args = "varkw"


class JsonRpcError(Exception):
    """
    >>> exc = JsonRpcError(1, JsonRpcConsumer.INVALID_REQUEST)
    >>> str(exc)
    '{
        "jsonrpc": "2.0",
        "id": 1,
        "error": {"message": "Invalid Request", "code": -32600},
    }'

    """

    def __init__(self, rpc_id, code, data=None):
        self.rpc_id = rpc_id
        self.code = code
        self.data = data

    @property
    def message(self):
        return RpcBase.errors[self.code]

    def as_dict(self):
        return RpcBase.error(self.rpc_id, self.code, self.message, self.data)

    def __str__(self):
        return json.dumps(self.as_dict())


class MethodNotSupportedError(Exception):
    pass


class RpcBase:
    """
    Variant of WebsocketConsumer that automatically JSON-encodes and decodes
    messages as they come in and go out. Expects everything to be text; will
    error on binary data.

    http://groups.google.com/group/json-rpc/web/json-rpc-2-0
    errors:
    code 	message 	meaning
    -32700 	Parse error 	Invalid JSON was received by the server.
            An error occurred on the server while parsing the JSON text.
    -32600 	Invalid Request 	The JSON sent is not a valid Request object.
    -32601 	Method not found 	The method does not exist / is not available.
    -32602 	Invalid params 	Invalid method parameter(s).
    -32603 	Internal error 	Internal JSON-RPC error.
    -32099 to -32000
            Server error 	Reserved for implementation-defined server-errors. (@TODO)

    """

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603
    GENERIC_APPLICATION_ERROR = -32000
    PARSE_RESULT_ERROR = -32701
    errors = {}
    errors[PARSE_ERROR] = "Parse Error"
    errors[INVALID_REQUEST] = "Invalid Request"
    errors[METHOD_NOT_FOUND] = "Method Not Found"
    errors[INVALID_PARAMS] = "Invalid Params"
    errors[INTERNAL_ERROR] = "Internal Error"
    errors[GENERIC_APPLICATION_ERROR] = "Application Error"
    errors[PARSE_RESULT_ERROR] = "Error while parsing result"

    _http_codes = {
        PARSE_ERROR: 500,
        INVALID_REQUEST: 400,
        METHOD_NOT_FOUND: 404,
        INVALID_PARAMS: 500,
        INTERNAL_ERROR: 500,
        GENERIC_APPLICATION_ERROR: 500,
    }

    available_rpc_methods = {}
    available_rpc_notifications = {}

    @classmethod
    def rpc_method(cls, rpc_name=None, *, websocket=True, http=True):
        """
        Decorator to list RPC methods available. An optional name and protocol
        rectrictions can be added.
        :param rpc_name: RPC name for the function
        :param bool websocket: if websocket transport can use this function
        :param bool http:if http transport can use this function
        :return: decorated function
        """

        def wrap(f):
            name = rpc_name if rpc_name is not None else f.__name__
            cid = id(cls)
            if cid not in cls.available_rpc_methods:
                cls.available_rpc_methods[cid] = {}
            f.options = dict(websocket=websocket, http=http)
            cls.available_rpc_methods[cid][name] = f

            return f

        return wrap

    @classmethod
    def get_rpc_methods(cls):
        """
        Returns the RPC methods available for this consumer
        :return: list
        """
        if id(cls) not in cls.available_rpc_methods:
            return []
        return list(cls.available_rpc_methods[id(cls)].keys())

    @classmethod
    def rpc_notification(cls, rpc_name=None, *, websocket=True, http=True):
        """
        Decorator to list RPC notifications available. An optional name can be added
        :param rpc_name: RPC name for the function
        :param bool websocket: if websocket transport can use this function
        :param bool http:if http transport can use this function
        :return: decorated function
        """

        def wrap(f):
            name = rpc_name if rpc_name is not None else f.__name__
            cid = id(cls)
            if cid not in cls.available_rpc_notifications:
                cls.available_rpc_notifications[cid] = {}
            f.options = dict(websocket=websocket, http=http)
            cls.available_rpc_notifications[cid][name] = f
            return f

        return wrap

    @classmethod
    def get_rpc_notifications(cls):
        """
        Returns the RPC methods available for this consumer
        :return: list
        """
        if id(cls) not in cls.available_rpc_notifications:
            return []
        return list(cls.available_rpc_notifications[id(cls)].keys())

    @staticmethod
    def json_rpc_frame(_id=None, result=None, params=None, method=None, error=None):
        frame = {"jsonrpc": "2.0"}
        if _id is not None:
            frame["id"] = _id
        if method:
            frame["method"] = method
            frame["params"] = params
        elif result is not None:
            frame["result"] = result
        elif error is not None:
            frame["error"] = error

        return frame

    @staticmethod
    def error(_id, code, message, data=None):
        """
        Error-type answer generator
        :param _id: int
        :param code: code of the error
        :param message: message for the error
        :param data: (optional) error data
        :return: object
        """
        error = {"code": code, "message": message}
        if data is not None:
            error["data"] = data

        return RpcBase.json_rpc_frame(error=error, _id=_id)

    def notify_channel(self, method, params):
        """
        Notify a group. Using JSON-RPC notificatons
        :param reply_channel: Reply channel
        :param method: JSON-RPC method
        :param params: parmas of the method
        :return:
        """
        content = self.json_rpc_frame(method=method, params=params)
        self.send(self.encode_json(content))

    def _get_method(self, data, is_notification):
        if data.get("jsonrpc") != "2.0":
            raise JsonRpcError(data.get("id"), self.INVALID_REQUEST)

        if "method" not in data:
            raise JsonRpcError(data.get("id"), self.INVALID_REQUEST)

        method_name = data["method"]
        if not isinstance(method_name, string_types):
            raise JsonRpcError(data.get("id"), self.INVALID_REQUEST)

        if method_name.startswith("_"):
            raise JsonRpcError(data.get("id"), self.METHOD_NOT_FOUND)

        try:
            if is_notification:
                method = self.__class__.available_rpc_notifications[id(self.__class__)][
                    method_name
                ]
            else:
                method = self.__class__.available_rpc_methods[id(self.__class__)][
                    method_name
                ]
            # Test if the websocket o http header was at false
            proto = self.scope["type"]
            if not method.options[proto]:
                msg = f"Method not available through {proto}"
                raise MethodNotSupportedError(msg)
        except (KeyError, MethodNotSupportedError) as e:
            raise JsonRpcError(data.get("id"), self.METHOD_NOT_FOUND) from e

        return method

    def _get_params(self, data):
        params = data.get("params", [])
        if not isinstance(params, (list, dict)):
            raise JsonRpcError(data.get("id"), self.INVALID_PARAMS)
        return params

    def __process(self, data, *, is_notification=False):
        """
        Process the received data
        :param dict data:
        :param channels.message.Message original_msg:
        :param bool is_notification:
        :return: dict
        """
        method = self._get_method(data, is_notification=is_notification)
        params = self._get_params(data)

        # log call in debug mode
        if settings.DEBUG:
            logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")

        result = self.__get_result(method, params)

        # check and pack result
        if not is_notification:
            # log call in debug mode
            if settings.DEBUG:
                logger.debug("Execution result: %s", result)

            result = self.json_rpc_frame(result=result, _id=data.get("id"))
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None

        return result

    def _handle(self, data):
        """
        Handle
        :param data:
        :return:
        """
        result = None
        is_notification = False

        if data is None:
            result = self.error(
                None, self.INVALID_REQUEST, self.errors[self.INVALID_REQUEST]
            )

        elif isinstance(data, dict):
            try:
                if data.get("method") is not None and data.get("id") is None:
                    is_notification = True
                result = self.__process(data, is_notification)
            except JsonRpcError as e:
                result = e.as_dict()
            except Exception as e:
                logger.debug("Application error: %s", e)
                result = self.error(
                    data.get("id"),
                    self.GENERIC_APPLICATION_ERROR,
                    str(e),
                    e.args[0] if len(e.args) == 1 else e.args,
                )
        elif isinstance(data, list):
            # TODO: implement batch calls
            if len([x for x in data if not isinstance(x, dict)]):
                result = self.error(
                    None, self.INVALID_REQUEST, self.errors[self.INVALID_REQUEST]
                )

        return result, is_notification

    def __get_result(self, method, params):
        func_args = getattr(getfullargspec(method), keywords_args)
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

    def _base_receive_json(self, content):
        """
        Called when receiving a message.
        :param message: message received
        :param kwargs:
        :return:
        """
        result, is_notification = self._handle(content)

        # Send response back only if it is a call, not notification
        if not is_notification:
            self.send_json(result)


class AsyncRpcBase(RpcBase):
    async def __get_result(self, method, params):
        func_args = getattr(getfullargspec(method), keywords_args)
        if func_args and "kwargs" in func_args:
            return (
                await method(*params, consumer=self)
                if isinstance(params, list)
                else await method(**params, consumer=self)
            )
        elif isinstance(params, list):
            return await method(*params)
        else:
            return await method(**params)

    async def __process(self, data, *, is_notification=False):
        """
        Process the received data
        :param dict data:
        :param channels.message.Message original_msg:
        :param bool is_notification:
        :return: dict
        """

        method = self._get_method(data, is_notification=is_notification)
        params = self._get_params(data)

        # log call in debug mode
        if settings.DEBUG:
            logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")

        result = await self.__get_result(method, params)

        # check and pack result
        if not is_notification:
            # log call in debug mode
            if settings.DEBUG:
                logger.debug("Execution result: %s", result)

            result = self.json_rpc_frame(result=result, _id=data.get("id"))
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None

        return result

    async def _handle(self, data):
        """
        Handle
        :param data:
        :return:
        """
        result = None
        is_notification = False

        if data is None:
            result = self.error(
                None, self.INVALID_REQUEST, self.errors[self.INVALID_REQUEST]
            )

        elif isinstance(data, dict):
            try:
                if data.get("method") is not None and data.get("id") is None:
                    is_notification = True
                result = await self.__process(data, is_notification)
            except JsonRpcError as e:
                result = e.as_dict()
            except Exception as e:
                logger.debug("Application error: %s", e)
                result = self.error(
                    data.get("id"),
                    self.GENERIC_APPLICATION_ERROR,
                    str(e),
                    e.args[0] if len(e.args) == 1 else e.args,
                )
        elif isinstance(data, list):
            # TODO: implement batch calls
            if len([x for x in data if not isinstance(x, dict)]):
                result = self.error(
                    None, self.INVALID_REQUEST, self.errors[self.INVALID_REQUEST]
                )

        return result, is_notification

    async def _base_receive_json(self, content):
        """
        Called when receiving a message.
        :param content: message received
        :return:
        """
        result, is_notification = await self._handle(content)

        # Send response back only if it is a call, not notification
        if not is_notification:
            await self.send_json(result)


class JsonRpcWebsocketConsumer(JsonWebsocketConsumer, RpcBase):
    def decode_json(self, data):
        try:
            return json.loads(data)
        except json.decoder.JSONDecodeError:
            frame = self.error(None, self.PARSE_ERROR, self.errors[self.PARSE_ERROR])
            self.send_json(frame)
            return None

    def encode_json(self, data):
        try:
            return json.dumps(data)
        except TypeError:
            frame = self.error(
                None,
                self.PARSE_ERROR,
                self.errors[self.PARSE_RESULT_ERROR],
                str(data["result"]),
            )
            return json.dumps(frame)

    def receive_json(self, content):
        self._base_receive_json(content)


class AsyncJsonRpcWebsocketConsumer(AsyncJsonWebsocketConsumer, AsyncRpcBase):
    async def receive_json(self, content):
        await self._base_receive_json(content)


class AsyncRpcHttpConsumer(AsyncHttpConsumer, RpcBase):
    async def handle(self, body):
        """
        Called on HTTP request
        :param message: message received
        :return:
        """
        if body:
            try:
                data = json.loads(body)
            except ValueError:
                # json could not decoded
                result = self.error(
                    None, self.PARSE_ERROR, self.errors[self.PARSE_ERROR]
                )
            else:
                result, is_notification = self._handle(data)

            # Set response status code
            # http://www.jsonrpc.org/historical/json-rpc-over-http.html#response-codes
            if is_notification:
                # notification response
                status_code = 204
                if result and "error" in result:
                    status_code = self._http_codes[result["error"]["code"]]
                result = ""
            elif "error" in result:
                status_code = self._http_codes[result["error"]["code"]]
            else:
                status_code = 200
        else:
            result = self.error(
                None, self.INVALID_REQUEST, self.errors[self.INVALID_REQUEST]
            )

        self.send_response(
            status_code,
            json.dumps(result),
            headers=[
                (b"Content-Type", b"application/json-rpc"),
            ],
        )
