"""Exceptions for the channels-rpc package."""
import json
from typing import Any

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


def generate_error_response(
    rpc_id: int, code: int, message: str, data=None
) -> dict[str, Any]:
    """Generate a JSON-RPC error response.

    Parameters
    ----------
    rpc_id : int
        Call ID.
    code : int
        RPC error code.
    message : str
        Error message.
    data : Any, optional
        Additional error data, by default None.

    Returns
    -------
    dict[str, Any]
        Error response.
    """
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return create_json_rpc_frame(error=error, rpc_id=rpc_id)


class JsonRpcError(Exception):
    """General JSON-RPC exception class."""

    def __init__(self, rpc_id: int, code: int):
        """Initialize a new :class:`JsonRpcError` instance.

        Parameters
        ----------
        rpc_id : int
            Call ID.
        code : int
            RPC error code.
        data : _type_, optional
            _description_, by default None
        """
        self.rpc_id = rpc_id
        self.code = code

    def as_dict(self) -> dict[str, Any]:
        """Return an error response dictionary.

        Returns
        -------
        dict[str, Any]
            Error response.
        """
        message = RPC_ERRORS[self.code]
        return generate_error_response(
            rpc_id=self.rpc_id, code=self.code, message=message
        )

    def __str__(self) -> str:
        """Error response dictionary as a string.

        Returns
        -------
        str
            Error response.
        """
        return json.dumps(self.as_dict())
