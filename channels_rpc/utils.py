from __future__ import annotations

from typing import Any


def create_json_rpc_frame(
    rpc_id: int | None = None,
    result: Any = None,
    params: dict[str, Any] | None = None,
    method: str | None = None,
    error: dict[str, int | str] | None = None,
) -> dict[str, Any]:
    frame = {"jsonrpc": "2.0"}
    if rpc_id is not None:
        frame["id"] = rpc_id
    if method:
        frame["method"] = method
        frame["params"] = params
    elif result is not None:
        frame["result"] = result
    elif error is not None:
        frame["error"] = error
    return frame
