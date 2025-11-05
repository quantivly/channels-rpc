"""Integration tests for WebSocket RPC consumers.

Coverage: AsyncJsonRpcWebsocketConsumer.
Target: 40-50 tests, 85%+ coverage of WebSocket consumer implementations.

CRITICAL TESTS - End-to-end WebSocket RPC functionality:
- WebSocket connection lifecycle (connect, disconnect)
- RPC method calls over WebSocket
- Notification handling over WebSocket
- JSON encoding/decoding with error handling
- Real message exchange between client and server
"""

from __future__ import annotations

import pytest
from channels.testing import WebsocketCommunicator

from channels_rpc import AsyncJsonRpcWebsocketConsumer
from channels_rpc.context import RpcContext

# ============================================================================
# Async WebSocket Consumer Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.websocket
class TestAsyncJsonRpcWebsocketConsumer:
    """Test asynchronous WebSocket RPC consumer."""

    @pytest.mark.asyncio
    async def test_async_websocket_connection_lifecycle(self):
        """Should connect and disconnect properly."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        connected, _ = await communicator.connect()

        assert connected

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_async_rpc_method_call_over_websocket(self):
        """Should execute async RPC method and return result."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def async_multiply(x: int, y: int) -> int:
            return x * y

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {
                "jsonrpc": "2.0",
                "method": "async_multiply",
                "params": {"x": 7, "y": 8},
                "id": 1,
            }
        )

        response = await communicator.receive_json_from()

        assert response["jsonrpc"] == "2.0"
        assert response["result"] == 56
        assert response["id"] == 1

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_async_notification_over_websocket(self):
        """Should handle async notification without response."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_notification()
        async def async_notify(message: str) -> None:
            pass

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {
                "jsonrpc": "2.0",
                "method": "async_notify",
                "params": {"message": "test"},
            }
        )

        # Should not receive any response
        import asyncio

        try:
            await asyncio.wait_for(communicator.receive_json_from(), timeout=0.1)
            msg = "Should not receive response for notification"
            raise AssertionError(msg)
        except asyncio.TimeoutError:
            pass

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_async_method_not_found_error(self):
        """Should return METHOD_NOT_FOUND error for unknown async method."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {"jsonrpc": "2.0", "method": "unknown_async_method", "id": 1}
        )

        response = await communicator.receive_json_from()

        assert "error" in response
        assert response["error"]["code"] == -32601

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_async_multiple_sequential_calls(self):
        """Should handle multiple sequential async RPC calls."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def async_add(a: int, b: int) -> int:
            return a + b

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        for i in range(3):
            await communicator.send_json_to(
                {
                    "jsonrpc": "2.0",
                    "method": "async_add",
                    "params": {"a": i, "b": i + 1},
                    "id": i,
                }
            )
            response = await communicator.receive_json_from()
            assert response["result"] == i + (i + 1)

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_async_method_with_complex_params(self):
        """Should handle async methods with complex nested parameters."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def process_data(data: dict) -> int:
            return len(data.get("items", []))

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {
                "jsonrpc": "2.0",
                "method": "process_data",
                "params": {
                    "data": {
                        "items": [1, 2, 3, 4, 5],
                        "metadata": {"type": "test"},
                    }
                },
                "id": 1,
            }
        )

        response = await communicator.receive_json_from()

        assert response["result"] == 5

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_async_invalid_json_handling(self):
        """Should disconnect on invalid JSON in async consumer (no error handling)."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        # Send invalid JSON - async consumer raises JSONDecodeError
        # This causes the connection to fail/close
        await communicator.send_to(text_data="not valid json")

        # The connection should close or raise an error
        # AsyncJsonRpcWebsocketConsumer doesn't override decode_json like sync version
        import asyncio

        with pytest.raises((asyncio.TimeoutError, Exception)):
            # Expect no response or connection closure
            await asyncio.wait_for(communicator.receive_json_from(), timeout=0.1)

        # Try to disconnect gracefully
        try:
            await communicator.disconnect()
        except Exception:  # noqa: S110
            pass  # Connection may already be closed

    @pytest.mark.asyncio
    async def test_async_invalid_request_format(self):
        """Should return INVALID_REQUEST for malformed async requests."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        # Wrong JSON-RPC version
        await communicator.send_json_to({"jsonrpc": "1.0", "method": "test", "id": 1})

        response = await communicator.receive_json_from()

        assert "error" in response
        assert response["error"]["code"] == -32600

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_async_custom_json_encoder(self):
        """Should use custom JSON encoder when provided in async consumer."""
        import json
        from datetime import datetime

        class DateTimeEncoder(json.JSONEncoder):
            def default(self, obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                return super().default(obj)

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            json_encoder_class = DateTimeEncoder

        @TestAsyncConsumer.rpc_method()
        async def get_async_time():
            return {"timestamp": datetime(2024, 12, 25, 18, 45, 30)}

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {"jsonrpc": "2.0", "method": "get_async_time", "id": 1}
        )

        response = await communicator.receive_json_from()

        assert "result" in response
        assert response["result"]["timestamp"] == "2024-12-25T18:45:30"
        assert response["id"] == 1

        await communicator.disconnect()


# ============================================================================
# Consumer Feature Tests
# ============================================================================


@pytest.mark.integration
@pytest.mark.websocket
class TestWebSocketConsumerFeatures:
    """Test specific WebSocket consumer features."""

    @pytest.mark.asyncio
    async def test_consumer_injection_async(self):
        """Should inject consumer instance in async methods via RpcContext."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def get_consumer_info(ctx: RpcContext) -> dict:
            return {
                "has_consumer": ctx.consumer is not None,
                "type": ctx.consumer.__class__.__name__,
            }

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {"jsonrpc": "2.0", "method": "get_consumer_info", "id": 1}
        )

        response = await communicator.receive_json_from()

        assert response["result"]["has_consumer"] is True
        assert response["result"]["type"] == "TestAsyncConsumer"

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_method_returning_false_async(self):
        """Should handle async methods returning False."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def returns_false():
            return False

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {"jsonrpc": "2.0", "method": "returns_false", "id": 1}
        )

        response = await communicator.receive_json_from()

        assert response["result"] is False

        await communicator.disconnect()

    @pytest.mark.asyncio
    async def test_method_exception_handling_async(self):
        """Should handle exceptions in async methods without leaking details."""

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def async_raises_error():
            msg = "Async error"
            # Use ValueError (domain error) instead of RuntimeError (indicates bug)
            raise ValueError(msg)

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        await communicator.send_json_to(
            {"jsonrpc": "2.0", "method": "async_raises_error", "id": 1}
        )

        response = await communicator.receive_json_from()

        assert "error" in response
        assert response["error"]["code"] == -32000
        # Security fix: error details should not be leaked
        assert response["error"]["message"] == "Application error occurred"
        assert "data" not in response["error"] or response["error"]["data"] is None

        await communicator.disconnect()
