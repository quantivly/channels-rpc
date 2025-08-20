from __future__ import annotations

from typing import Any

FRAME_BASE: dict[str, Any] = {"jsonrpc": "2.0"}


def create_json_rpc_frame(
    rpc_id: int | None = None,
    result: Any = None,
    params: dict[str, Any] | None = None,
    method: str | None = None,
    error: dict[str, int | str] | None = None,
    rpc_id_key: str = "call_id",
    *,
    compressed: bool = False,
) -> dict[str, Any]:
    frame = FRAME_BASE.copy()
    if result is None:
        return {
            "request": {
                rpc_id_key: rpc_id,
                "method": method,
                "arguments": params or {},
            },
            **frame,
        }
    else:
        return {
            "request": {
                rpc_id_key: rpc_id,
                "method": method,
                "arguments": params or {},
            },
            "response": {
                "result": result or error,
                "result_type": type(result).__name__ if result else None,
                "compressed": compressed,
                rpc_id_key: rpc_id,
            },
            **frame,
        }
