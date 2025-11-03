"""Helper utilities for WebSocket testing."""

from __future__ import annotations

from contextlib import asynccontextmanager

from channels.testing import WebsocketCommunicator


@asynccontextmanager
async def websocket_connection(consumer_class, path="/ws/"):
    """Context manager for WebSocket connections.

    Usage:
        async with websocket_connection(MyConsumer) as ws:
            await ws.send_json_to({...})
            response = await ws.receive_json_from()
    """
    communicator = WebsocketCommunicator(consumer_class.as_asgi(), path)
    connected, _ = await communicator.connect()
    assert connected, "WebSocket connection failed"

    try:
        yield communicator
    finally:
        await communicator.disconnect()


async def send_rpc_request(communicator, method, params=None, rpc_id=1):
    """Send a JSON-RPC 2.0 request over WebSocket.

    Parameters
    ----------
    communicator : WebsocketCommunicator
        Active WebSocket connection
    method : str
        RPC method name
    params : dict | list, optional
        Method parameters
    rpc_id : int | str | None, optional
        Request ID (None for notification)

    Returns
    -------
    dict | None
        JSON-RPC response (None for notifications)
    """
    request = {
        "jsonrpc": "2.0",
        "method": method,
    }
    if params is not None:
        request["params"] = params
    if rpc_id is not None:
        request["id"] = rpc_id

    await communicator.send_json_to(request)

    # Notifications don't expect responses
    if rpc_id is None:
        return None

    return await communicator.receive_json_from()


async def assert_rpc_success(communicator, method, params, expected_result, rpc_id=1):
    """Assert that RPC call succeeds with expected result.

    This is a high-level helper for common test pattern.
    """
    response = await send_rpc_request(communicator, method, params, rpc_id)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == rpc_id
    assert "result" in response
    assert response["result"] == expected_result
    assert "error" not in response


async def assert_rpc_error(communicator, method, params, expected_code, rpc_id=1):
    """Assert that RPC call returns error with expected code."""
    response = await send_rpc_request(communicator, method, params, rpc_id)

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == rpc_id
    assert "error" in response
    assert response["error"]["code"] == expected_code
    assert "result" not in response
