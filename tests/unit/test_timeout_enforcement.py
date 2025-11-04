"""Tests for RPC method timeout enforcement.

Coverage: Timeout enforcement for RPC methods to prevent DoS attacks from
long-running methods.
"""

from __future__ import annotations

import asyncio

import pytest

from channels_rpc.async_rpc_base import MAX_METHOD_EXECUTION_TIME, AsyncRpcBase
from channels_rpc.context import RpcContext
from channels_rpc.exceptions import JsonRpcErrorCode
from channels_rpc.registry import get_registry


@pytest.fixture
def async_consumer_with_timeout_methods(mock_websocket_scope):
    """Async consumer with methods having various timeout configurations."""

    class MockAsyncConsumer(AsyncRpcBase):
        def __init__(self, scope=None):
            self.scope = scope or {"type": "websocket"}
            self.sent_messages = []

        async def send_json(self, data):  # type: ignore[override]
            self.sent_messages.append(data)

        async def send(self, data):  # type: ignore[override]
            self.sent_messages.append(data)

        def encode_json(self, data):
            import json

            return json.dumps(data)

    class TestConsumer(MockAsyncConsumer):
        pass

    @TestConsumer.rpc_method()
    async def default_timeout_method() -> str:
        """Method with default timeout (300s)."""
        await asyncio.sleep(0.1)  # Fast completion
        return "success"

    @TestConsumer.rpc_method(timeout=1.0)
    async def custom_timeout_method() -> str:
        """Method with custom 1-second timeout."""
        await asyncio.sleep(0.1)  # Fast completion
        return "success"

    @TestConsumer.rpc_method(timeout=0.1)
    async def short_timeout_method() -> str:
        """Method with very short timeout that will be exceeded."""
        await asyncio.sleep(0.5)  # Too slow
        return "should_not_reach_here"

    @TestConsumer.rpc_method(timeout=0)
    async def no_timeout_method() -> str:
        """Method with timeout disabled (timeout=0)."""
        await asyncio.sleep(0.2)
        return "success"

    @TestConsumer.rpc_method(timeout=-1)
    async def negative_timeout_method() -> str:
        """Method with negative timeout (disabled)."""
        await asyncio.sleep(0.2)
        return "success"

    @TestConsumer.database_rpc_method(timeout=0.5)
    def database_method_with_timeout(value: int) -> int:
        """Database method with custom timeout."""
        import time

        time.sleep(0.1)  # Fast completion
        return value * 2

    @TestConsumer.database_rpc_method(timeout=0.1)
    def database_method_exceeds_timeout(value: int) -> int:
        """Database method that exceeds timeout."""
        import time

        time.sleep(0.5)  # Too slow
        return value * 2

    return TestConsumer(mock_websocket_scope)


@pytest.mark.unit
class TestTimeoutEnforcement:
    """Test RPC method timeout enforcement."""

    @pytest.mark.asyncio
    async def test_default_timeout_applied(self, async_consumer_with_timeout_methods):
        """Should apply default timeout (300s) when none specified."""
        registry = get_registry()
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__, "default_timeout_method"
        )

        # Verify wrapper has None for timeout (will use default)
        assert method.timeout is None

        # Execute method successfully (completes in 0.1s, well under 300s)
        request = {
            "jsonrpc": "2.0",
            "method": "default_timeout_method",
            "params": {},
            "id": 1,
        }

        response = await async_consumer_with_timeout_methods._process_call(request)

        assert response is not None
        assert response["result"] == "success"
        assert response["id"] == 1

    @pytest.mark.asyncio
    async def test_custom_timeout_applied(self, async_consumer_with_timeout_methods):
        """Should apply custom timeout when specified in decorator."""
        registry = get_registry()
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__, "custom_timeout_method"
        )

        # Verify wrapper has custom timeout
        assert method.timeout == 1.0

        # Execute method successfully (completes in 0.1s, under 1s)
        request = {
            "jsonrpc": "2.0",
            "method": "custom_timeout_method",
            "params": {},
            "id": 2,
        }

        response = await async_consumer_with_timeout_methods._process_call(request)

        assert response is not None
        assert response["result"] == "success"
        assert response["id"] == 2

    @pytest.mark.asyncio
    async def test_timeout_exceeded_raises_error(
        self, async_consumer_with_timeout_methods
    ):
        """Should raise JsonRpcError when method exceeds timeout."""
        request = {
            "jsonrpc": "2.0",
            "method": "short_timeout_method",
            "params": {},
            "id": 3,
        }

        # Method sleeps for 0.5s but timeout is 0.1s
        # Should raise JsonRpcError with INTERNAL_ERROR code
        from channels_rpc.exceptions import JsonRpcError

        with pytest.raises(JsonRpcError) as exc_info:
            await async_consumer_with_timeout_methods._process_call(request)

        error = exc_info.value
        assert error.code == JsonRpcErrorCode.INTERNAL_ERROR
        assert error.data is not None
        assert "timeout" in error.data
        assert error.data["timeout"] == 0.1

        # Check that as_dict() generates proper error message
        error_dict = error.as_dict()
        assert "timed out" in error_dict["error"]["message"].lower()
        assert "0.1" in error_dict["error"]["message"]

    @pytest.mark.asyncio
    async def test_timeout_zero_disables_enforcement(
        self, async_consumer_with_timeout_methods
    ):
        """Should disable timeout enforcement when timeout=0."""
        registry = get_registry()
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__, "no_timeout_method"
        )

        # Verify wrapper has timeout=0
        assert method.timeout == 0

        # Execute method successfully (no timeout enforced)
        request = {
            "jsonrpc": "2.0",
            "method": "no_timeout_method",
            "params": {},
            "id": 4,
        }

        response = await async_consumer_with_timeout_methods._process_call(request)

        assert response is not None
        assert response["result"] == "success"
        assert response["id"] == 4

    @pytest.mark.asyncio
    async def test_negative_timeout_disables_enforcement(
        self, async_consumer_with_timeout_methods
    ):
        """Should disable timeout enforcement when timeout is negative."""
        registry = get_registry()
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__, "negative_timeout_method"
        )

        # Verify wrapper has negative timeout
        assert method.timeout == -1

        # Execute method successfully (no timeout enforced)
        request = {
            "jsonrpc": "2.0",
            "method": "negative_timeout_method",
            "params": {},
            "id": 5,
        }

        response = await async_consumer_with_timeout_methods._process_call(request)

        assert response is not None
        assert response["result"] == "success"
        assert response["id"] == 5

    @pytest.mark.asyncio
    async def test_database_method_timeout(self, async_consumer_with_timeout_methods):
        """Should enforce timeout on database_rpc_method decorated methods."""
        registry = get_registry()
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__,
            "database_method_with_timeout",
        )

        # Verify wrapper has custom timeout
        assert method.timeout == 0.5

        # Execute method successfully (completes in 0.1s, under 0.5s)
        request = {
            "jsonrpc": "2.0",
            "method": "database_method_with_timeout",
            "params": {"value": 5},
            "id": 6,
        }

        response = await async_consumer_with_timeout_methods._process_call(request)

        assert response is not None
        assert response["result"] == 10
        assert response["id"] == 6

    @pytest.mark.asyncio
    async def test_database_method_timeout_exceeded(
        self, async_consumer_with_timeout_methods
    ):
        """Should timeout database methods that exceed limit."""
        request = {
            "jsonrpc": "2.0",
            "method": "database_method_exceeds_timeout",
            "params": {"value": 5},
            "id": 7,
        }

        # Method sleeps for 0.5s but timeout is 0.1s
        from channels_rpc.exceptions import JsonRpcError

        with pytest.raises(JsonRpcError) as exc_info:
            await async_consumer_with_timeout_methods._process_call(request)

        error = exc_info.value
        assert error.code == JsonRpcErrorCode.INTERNAL_ERROR
        assert error.data is not None
        assert "timeout" in error.data

        error_dict = error.as_dict()
        assert "timed out" in error_dict["error"]["message"].lower()

    @pytest.mark.asyncio
    async def test_timeout_error_includes_rpc_id(
        self, async_consumer_with_timeout_methods
    ):
        """Should include RPC ID in timeout error for request tracking."""
        request = {
            "jsonrpc": "2.0",
            "method": "short_timeout_method",
            "params": {},
            "id": "test-request-123",
        }

        from channels_rpc.exceptions import JsonRpcError

        with pytest.raises(JsonRpcError) as exc_info:
            await async_consumer_with_timeout_methods._process_call(request)

        error = exc_info.value
        assert error.rpc_id == "test-request-123"

    @pytest.mark.asyncio
    async def test_timeout_error_includes_timeout_data(
        self, async_consumer_with_timeout_methods
    ):
        """Should include timeout data for informative error message."""
        request = {
            "jsonrpc": "2.0",
            "method": "short_timeout_method",
            "params": {},
            "id": 8,
        }

        from channels_rpc.exceptions import JsonRpcError

        with pytest.raises(JsonRpcError) as exc_info:
            await async_consumer_with_timeout_methods._process_call(request)

        error = exc_info.value
        # Should include timeout in data field for error message generation
        assert error.data is not None
        assert "timeout" in error.data
        assert error.data["timeout"] == 0.1


@pytest.mark.unit
class TestTimeoutConfiguration:
    """Test timeout configuration mechanics."""

    def test_default_timeout_constant(self):
        """Should have default timeout constant defined."""
        assert MAX_METHOD_EXECUTION_TIME == 300
        assert isinstance(MAX_METHOD_EXECUTION_TIME, int)

    @pytest.mark.asyncio
    async def test_timeout_metadata_stored_in_wrapper(
        self, async_consumer_with_timeout_methods
    ):
        """Should store timeout value in RpcMethodWrapper."""
        registry = get_registry()

        # Check default (None)
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__, "default_timeout_method"
        )
        assert method.timeout is None

        # Check custom timeout
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__, "custom_timeout_method"
        )
        assert method.timeout == 1.0

        # Check disabled timeout
        method = registry.get_method(
            async_consumer_with_timeout_methods.__class__, "no_timeout_method"
        )
        assert method.timeout == 0

    @pytest.mark.asyncio
    async def test_timeout_with_context_injection(
        self, async_consumer_with_timeout_methods
    ):
        """Should enforce timeout on methods that accept RpcContext."""

        class TestConsumer(AsyncRpcBase):
            def __init__(self, scope=None):
                self.scope = scope or {"type": "websocket"}
                self.sent_messages = []

            async def send_json(self, data):  # type: ignore[override]
                self.sent_messages.append(data)

            async def send(self, data):  # type: ignore[override]
                self.sent_messages.append(data)

            def encode_json(self, data):
                import json

                return json.dumps(data)

        @TestConsumer.rpc_method(timeout=0.2)
        async def method_with_context(ctx: RpcContext, value: str) -> str:
            await asyncio.sleep(0.1)
            return f"Consumer: {ctx.consumer is not None}, Value: {value}"

        consumer = TestConsumer()
        request = {
            "jsonrpc": "2.0",
            "method": "method_with_context",
            "params": {"value": "test"},
            "id": 9,
        }

        response = await consumer._process_call(request)

        assert response is not None
        assert "Consumer: True" in response["result"]
        assert "Value: test" in response["result"]
