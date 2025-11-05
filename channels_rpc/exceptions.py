"""Exceptions for the channels-rpc package."""

import json
from enum import IntEnum
from typing import Any

from channels_rpc.utils import create_json_rpc_error_response


class JsonRpcErrorCode(IntEnum):
    """JSON-RPC 2.0 error codes.

    Standard error codes are defined by the JSON-RPC 2.0 specification.
    Server-defined error codes are in the range -32099 to -32000.

    Standard Attributes
    -------------------
    PARSE_ERROR : int
        Invalid JSON was received (-32700).
    INVALID_REQUEST : int
        The JSON sent is not a valid Request object (-32600).
    METHOD_NOT_FOUND : int
        The method does not exist / is not available (-32601).
    INVALID_PARAMS : int
        Invalid method parameter(s) (-32602).
    INTERNAL_ERROR : int
        Internal JSON-RPC error (-32603).

    Server-Defined Attributes
    -------------------------
    GENERIC_APPLICATION_ERROR : int
        Server-defined application error (-32000).
        **Deprecated**: Use more specific error codes instead.
    REQUEST_TOO_LARGE : int
        Server-defined error for oversized requests (-32001).
    PARSE_RESULT_ERROR : int
        Server-defined error for result parsing (-32701).
    """

    # Standard JSON-RPC 2.0 error codes
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # Server-defined error codes (-32099 to -32000, with -32701 extension)
    GENERIC_APPLICATION_ERROR = -32000  # Deprecated - use specific codes
    REQUEST_TOO_LARGE = -32001

    PARSE_RESULT_ERROR = -32701  # Extension


RPC_ERRORS: dict[int, str] = {
    # Standard JSON-RPC 2.0 errors
    JsonRpcErrorCode.PARSE_ERROR: "Parse Error",
    JsonRpcErrorCode.INVALID_REQUEST: "Invalid Request",
    JsonRpcErrorCode.METHOD_NOT_FOUND: "Method Not Found",
    JsonRpcErrorCode.INVALID_PARAMS: "Invalid Params",
    JsonRpcErrorCode.INTERNAL_ERROR: "Internal Error",
    # Server-defined errors
    JsonRpcErrorCode.GENERIC_APPLICATION_ERROR: "Application Error",
    JsonRpcErrorCode.REQUEST_TOO_LARGE: "Request Too Large",
    # Extensions
    JsonRpcErrorCode.PARSE_RESULT_ERROR: "Error while parsing result",
}


def generate_error_response(
    rpc_id: int | str | float | None, code: int, message: str, data=None
) -> dict[str, Any]:
    """Generate a JSON-RPC error response.

    Parameters
    ----------
    rpc_id : int | str | float | None
        Request ID this error responds to.
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
    return create_json_rpc_error_response(
        rpc_id=rpc_id, code=code, message=message, data=data
    )


class JsonRpcError(Exception):
    """General JSON-RPC exception class."""

    def __init__(self, rpc_id: str | int | float | None, code: int, data: Any = None):
        """Initialize a new :class:`JsonRpcError` instance.

        Parameters
        ----------
        rpc_id : str | int | float | None
            Call ID. Can be a string, integer, float, or None for requests
            without an ID.
        code : int
            RPC error code.
        data : Any, optional
            Additional error context data, by default None
        """
        self.rpc_id = rpc_id
        self.code = code
        self.data = data

    def as_dict(self) -> dict[str, Any]:
        """Return an error response dictionary.

        Returns
        -------
        dict[str, Any]
            Error response.
        """
        message = RPC_ERRORS[self.code]

        # Enhance error message with context from data
        if self.data:
            if self.code == JsonRpcErrorCode.METHOD_NOT_FOUND and isinstance(
                self.data, dict
            ):
                method = self.data.get("method")
                if method:
                    message = f"{message}: '{method}'"
            elif self.code == JsonRpcErrorCode.INVALID_REQUEST and isinstance(
                self.data, dict
            ):
                if "version" in self.data:
                    version = self.data["version"]
                    message = (
                        f"{message}: Invalid JSON-RPC version '{version}', "
                        "expected '2.0'"
                    )
                elif "field" in self.data:
                    message = f"{message}: {self.data['field']}"
            elif self.code == JsonRpcErrorCode.INVALID_PARAMS and isinstance(
                self.data, dict
            ):
                if "expected" in self.data and "actual" in self.data:
                    expected = self.data["expected"]
                    actual = self.data["actual"]
                    message = f"{message}: Expected {expected}, got {actual}"
            elif self.code == JsonRpcErrorCode.REQUEST_TOO_LARGE and isinstance(
                self.data, dict
            ):
                limit_type = self.data.get("limit_type", "unknown")
                limit = self.data.get("limit", "unknown")
                message = f"{message}: {limit_type} exceeds limit of {limit}"
            elif self.code == JsonRpcErrorCode.INTERNAL_ERROR and isinstance(
                self.data, dict
            ):
                if "timeout" in self.data:
                    timeout = self.data["timeout"]
                    message = (
                        f"{message}: Method execution timed out "
                        f"after {timeout:.1f} seconds"
                    )

        return generate_error_response(
            rpc_id=self.rpc_id, code=self.code, message=message, data=self.data
        )

    def __str__(self) -> str:
        """Error response dictionary as a string.

        Returns
        -------
        str
            Error response.
        """
        return json.dumps(self.as_dict())


class RequestTooLargeError(JsonRpcError):
    """Exception for requests exceeding size limits."""

    def __init__(
        self, rpc_id: str | int | float | None, limit_type: str, limit_value: int
    ):
        """Initialize RequestTooLargeError.

        Parameters
        ----------
        rpc_id : str | int | float | None
            Request ID.
        limit_type : str
            Type of limit exceeded (e.g., "message_size", "array_length").
        limit_value : int
            The limit that was exceeded.
        """
        super().__init__(
            rpc_id=rpc_id,
            code=JsonRpcErrorCode.REQUEST_TOO_LARGE,
            data={"limit_type": limit_type, "limit": limit_value},
        )
