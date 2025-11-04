"""Exceptions for the channels-rpc package."""

import json
from enum import IntEnum
from typing import Any

from channels_rpc.utils import create_json_rpc_error_response


class JsonRpcErrorCode(IntEnum):
    """JSON-RPC 2.0 error codes.

    Standard error codes are defined by the JSON-RPC 2.0 specification.
    Server-defined error codes are in the range -32099 to -32000.

    Error Code Categories
    ---------------------
    Client Errors (-32006 to -32002):
        These indicate problems with the request that the client should fix.
        Similar to HTTP 4xx errors. Retrying without changes will likely fail.

    Server Errors (-32099 to -32010):
        These indicate server-side issues that may be transient.
        Similar to HTTP 5xx errors. Retrying may succeed.

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
    VALIDATION_ERROR : int
        Client error: Invalid input data (-32002).
        Use when request data fails validation rules.
    RESOURCE_NOT_FOUND : int
        Client error: Requested resource doesn't exist (-32003).
        Use when a referenced entity cannot be found.
    PERMISSION_DENIED : int
        Client error: Authorization failure (-32004).
        Use when the client lacks required permissions.
    CONFLICT : int
        Client error: State conflict (-32005).
        Use when the operation conflicts with current state.
    RATE_LIMIT_EXCEEDED : int
        Client error: Too many requests (-32006).
        Use when rate limiting is applied.
    DATABASE_ERROR : int
        Server error: Transient database failure (-32010).
        Use for temporary database connection or query issues.
    EXTERNAL_SERVICE_ERROR : int
        Server error: External dependency failed (-32011).
        Use when external API or service calls fail.
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

    # Client errors (-32006 to -32002): Problems with the request
    VALIDATION_ERROR = -32002
    RESOURCE_NOT_FOUND = -32003
    PERMISSION_DENIED = -32004
    CONFLICT = -32005
    RATE_LIMIT_EXCEEDED = -32006

    # Server errors (-32099 to -32010): Server-side issues
    DATABASE_ERROR = -32010
    EXTERNAL_SERVICE_ERROR = -32011

    PARSE_RESULT_ERROR = -32701  # Extension

    @classmethod
    def is_client_error(cls, code: int) -> bool:
        """Check if error code indicates a client error.

        Client errors indicate problems with the request that the client
        should fix. Retrying without changes will likely fail.

        Parameters
        ----------
        code : int
            Error code to check.

        Returns
        -------
        bool
            True if the code represents a client error.
        """
        return -32006 <= code <= -32002

    @classmethod
    def is_server_error(cls, code: int) -> bool:
        """Check if error code indicates a server error.

        Server errors indicate server-side issues that may be transient.
        Retrying may succeed after a delay.

        Parameters
        ----------
        code : int
            Error code to check.

        Returns
        -------
        bool
            True if the code represents a server error.
        """
        return (-32099 <= code <= -32010) or code == -32603


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
    # Client errors
    JsonRpcErrorCode.VALIDATION_ERROR: "Validation Error",
    JsonRpcErrorCode.RESOURCE_NOT_FOUND: "Resource Not Found",
    JsonRpcErrorCode.PERMISSION_DENIED: "Permission Denied",
    JsonRpcErrorCode.CONFLICT: "Conflict",
    JsonRpcErrorCode.RATE_LIMIT_EXCEEDED: "Rate Limit Exceeded",
    # Server errors
    JsonRpcErrorCode.DATABASE_ERROR: "Database Error",
    JsonRpcErrorCode.EXTERNAL_SERVICE_ERROR: "External Service Error",
    # Extensions
    JsonRpcErrorCode.PARSE_RESULT_ERROR: "Error while parsing result",
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
            code=JsonRpcErrorCode.REQUEST_TOO_LARGE,
            data={"limit_type": limit_type, "limit": limit_value},
        )
