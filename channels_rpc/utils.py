from __future__ import annotations

from typing import Any


def create_json_rpc_request(
    rpc_id: str | int | None = None,
    method: str | None = None,
    params: dict[str, Any] | list[Any] | None = None,
) -> dict[str, Any]:
    """Create a JSON-RPC 2.0 request message.

    Parameters
    ----------
    rpc_id : str | int | None
        Request identifier. If None, creates a notification.
    method : str | None
        Method name to call.
    params : dict[str, Any] | list[Any] | None
        Parameters to pass to the method.

    Returns
    -------
    dict[str, Any]
        JSON-RPC 2.0 request message.
    """
    message = {
        "jsonrpc": "2.0",
        "method": method,
    }

    if rpc_id is not None:
        message["id"] = rpc_id

    if params is not None:
        message["params"] = params

    return message


def create_json_rpc_response(
    rpc_id: str | int | None = None,
    result: Any = None,
    error: dict[str, Any] | None = None,
    *,
    compressed: bool = False,
) -> dict[str, Any]:
    """Create a JSON-RPC 2.0 response message.

    Parameters
    ----------
    rpc_id : str | int | None
        Request identifier that this responds to.
    result : Any
        Successful result data.
    error : dict[str, Any] | None
        Error information if the request failed.
    compressed : bool
        Whether the result is compressed (extension field).

    Returns
    -------
    dict[str, Any]
        JSON-RPC 2.0 response message.
    """
    message = {
        "jsonrpc": "2.0",
        "id": rpc_id,
    }

    if error is not None:
        message["error"] = error
    else:
        message["result"] = result
        if compressed:
            message["compressed"] = True

    return message


def create_json_rpc_error_response(
    rpc_id: str | int | None = None,
    code: int = -32603,
    message: str = "Internal error",
    data: Any = None,
) -> dict[str, Any]:
    """Create a JSON-RPC 2.0 error response.

    Parameters
    ----------
    rpc_id : str | int | None
        Request identifier that this responds to.
    code : int
        Error code (see JSON-RPC 2.0 spec).
    message : str
        Error message.
    data : Any
        Additional error data.

    Returns
    -------
    dict[str, Any]
        JSON-RPC 2.0 error response message.
    """
    error_obj = {
        "code": code,
        "message": message,
    }

    if data is not None:
        error_obj["data"] = data

    return create_json_rpc_response(rpc_id=rpc_id, error=error_obj)


# Backward compatibility - deprecated
def create_json_rpc_frame(
    rpc_id: int | None = None,
    result: Any = None,
    params: dict[str, Any] | None = None,
    method: str | None = None,
    error: dict[str, int | str] | None = None,
    rpc_id_key: str = "call_id",  # noqa: ARG001
    *,
    compressed: bool = False,
) -> dict[str, Any]:
    """Legacy function for backward compatibility."""
    if result is None:
        # Creating a request
        return create_json_rpc_request(rpc_id=rpc_id, method=method, params=params)
    elif error:
        return create_json_rpc_error_response(
            rpc_id=rpc_id,
            code=error.get("code", -32603),
            message=error.get("message", "Internal error"),
            data=error.get("data"),
        )
    else:
        return create_json_rpc_response(
            rpc_id=rpc_id, result=result, compressed=compressed
        )
