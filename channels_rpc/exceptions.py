"""Exceptions for the channels-rpc package."""
import json

from channels_rpc.utils import create_json_rpc_frame

PARSE_ERROR: int = -32700
INVALID_REQUEST: int = -32600
METHOD_NOT_FOUND: int = -32601
INVALID_PARAMS: int = -32602
INTERNAL_ERROR: int = -32603
GENERIC_APPLICATION_ERROR: int = -32000
PARSE_RESULT_ERROR: int = -32701
RPC_ERRORS: dict[int, str] = {
    PARSE_ERROR: "Parse Error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method Not Found",
    INVALID_PARAMS: "Invalid Params",
    INTERNAL_ERROR: "Internal Error",
    GENERIC_APPLICATION_ERROR: "Application Error",
    PARSE_RESULT_ERROR: "Error while parsing result",
}


def generate_error_response(rpc_id: int, code: int, message: str, data=None):
    """Generate a JSON-RPC error response.

    Parameters
    ----------
    rpc_id : int
        RPC ID.
    code : int
        RPC error code.
    message : str
        Error message.
    data : _type_, optional
        Additional error data, by default None.

    Returns
    -------
    _type_
        _description_
    """
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return create_json_rpc_frame(error=error, rpc_id=rpc_id)


class MethodNotSupportedError(Exception):
    """Raised when a method (i.e., a called procedure) is not supported by the
    consumer."""

    pass


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

    def __init__(self, rpc_id: int, code: int, data=None):
        self.rpc_id = rpc_id
        self.code = code
        self.data = data

    def as_dict(self):
        message = RPC_ERRORS[self.code]
        return generate_error_response(
            rpc_id=self.rpc_id, code=self.code, message=message, data=self.data
        )

    def __str__(self):
        return json.dumps(self.as_dict())
