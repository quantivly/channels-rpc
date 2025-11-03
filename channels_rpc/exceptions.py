"""Exceptions for the channels-rpc package."""

import json
from typing import Any

from channels_rpc.utils import create_json_rpc_error_response

PARSE_ERROR: int = -32700
INVALID_REQUEST: int = -32600
METHOD_NOT_FOUND: int = -32601
INVALID_PARAMS: int = -32602
INTERNAL_ERROR: int = -32603
GENERIC_APPLICATION_ERROR: int = -32000
PARSE_RESULT_ERROR: int = -32701
REQUEST_TOO_LARGE: int = -32001  # Server-defined error code
RPC_ERRORS: dict[int, str] = {
    PARSE_ERROR: "Parse Error",
    INVALID_REQUEST: "Invalid Request",
    METHOD_NOT_FOUND: "Method Not Found",
    INVALID_PARAMS: "Invalid Params",
    INTERNAL_ERROR: "Internal Error",
    GENERIC_APPLICATION_ERROR: "Application Error",
    PARSE_RESULT_ERROR: "Error while parsing result",
    REQUEST_TOO_LARGE: "Request Too Large",
}


def generate_error_response(
    rpc_id: int | str | None, code: int, message: str, data=None
) -> dict[str, Any]:
    """Generate a JSON-RPC error response.

    Parameters
    ----------
    rpc_id : int | str | None
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

    def __init__(self, rpc_id: str | int | None, code: int, data: Any = None):
        """Initialize a new :class:`JsonRpcError` instance.

        Parameters
        ----------
        rpc_id : str | int | None
            Call ID. Can be a string, integer, or None for requests without an ID.
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
            if self.code == METHOD_NOT_FOUND and isinstance(self.data, dict):
                method = self.data.get("method")
                if method:
                    message = f"{message}: '{method}'"
            elif self.code == INVALID_REQUEST and isinstance(self.data, dict):
                if "version" in self.data:
                    version = self.data["version"]
                    message = (
                        f"{message}: Invalid JSON-RPC version '{version}', "
                        "expected '2.0'"
                    )
                elif "field" in self.data:
                    message = f"{message}: {self.data['field']}"
            elif self.code == INVALID_PARAMS and isinstance(self.data, dict):
                if "expected" in self.data and "actual" in self.data:
                    expected = self.data["expected"]
                    actual = self.data["actual"]
                    message = f"{message}: Expected {expected}, got {actual}"
            elif self.code == REQUEST_TOO_LARGE and isinstance(self.data, dict):
                limit_type = self.data.get("limit_type", "unknown")
                limit = self.data.get("limit", "unknown")
                message = f"{message}: {limit_type} exceeds limit of {limit}"

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

    def __init__(self, rpc_id: str | int | None, limit_type: str, limit_value: int):
        """Initialize RequestTooLargeError.

        Parameters
        ----------
        rpc_id : str | int | None
            Request ID.
        limit_type : str
            Type of limit exceeded (e.g., "message_size", "array_length").
        limit_value : int
            The limit that was exceeded.
        """
        super().__init__(
            rpc_id=rpc_id,
            code=REQUEST_TOO_LARGE,
            data={"limit_type": limit_type, "limit": limit_value},
        )
