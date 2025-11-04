"""Tests for async RPC processing logic in async_rpc_base.py.

Coverage: async execute_called_method(), process_call(), intercept_call(),
_base_receive_json().
Target: 40-50 tests, 90%+ coverage of async processing logic.

CRITICAL TESTS - Async variants of core RPC functionality:
- Async method execution with consumer injection
- Async call processing and result handling
- Async request/response routing
- Async notification handling
- Async error handling and response generation
"""

from __future__ import annotations

import pytest

from channels_rpc.async_rpc_base import AsyncRpcBase
from channels_rpc.exceptions import JsonRpcErrorCode


@pytest.mark.unit
class TestAsyncExecuteCalledMethod:
    """Test async execute_called_method() - async method invocation."""

    @pytest.mark.asyncio
    async def test_execute_with_dict_params(self, async_consumer_with_methods):
        """Should execute async method with dict params."""
        method = async_consumer_with_methods.rpc_methods[
            id(async_consumer_with_methods.__class__)
        ]["async_add"]
        params = {"a": 5, "b": 3}

        result = await async_consumer_with_methods._execute_called_method(
            method, params
        )

        assert result == 8

    @pytest.mark.asyncio
    async def test_execute_with_list_params(self, async_consumer_with_methods):
        """Should execute async method with list params."""
        method = async_consumer_with_methods.rpc_methods[
            id(async_consumer_with_methods.__class__)
        ]["async_add"]
        params = [7, 3]

        result = await async_consumer_with_methods._execute_called_method(
            method, params
        )

        assert result == 10

    @pytest.mark.asyncio
    async def test_execute_injects_consumer_for_kwargs(
        self, async_consumer_with_methods
    ):
        """Should inject consumer when async method accepts **kwargs."""
        method = async_consumer_with_methods.rpc_methods[
            id(async_consumer_with_methods.__class__)
        ]["async_echo"]
        params = {"message": "test"}

        result = await async_consumer_with_methods._execute_called_method(
            method, params
        )

        assert "consumer: True" in result

    @pytest.mark.asyncio
    async def test_execute_without_consumer_injection(
        self, async_consumer_with_methods
    ):
        """Should not inject consumer when async method doesn't accept **kwargs."""
        method = async_consumer_with_methods.rpc_methods[
            id(async_consumer_with_methods.__class__)
        ]["async_add"]
        params = {"a": 1, "b": 1}

        result = await async_consumer_with_methods._execute_called_method(
            method, params
        )

        assert result == 2


@pytest.mark.unit
class TestAsyncProcessCall:
    """Test async process_call() method - main async RPC call processing."""

    @pytest.mark.asyncio
    async def test_process_call_returns_result_dict(self, async_consumer_with_methods):
        """Should return JSON-RPC response dict for async method calls."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_add",
            "params": {"a": 3, "b": 5},
            "id": 1,
        }

        result = await async_consumer_with_methods._process_call(
            data, is_notification=False
        )

        assert isinstance(result, dict)
        assert result["jsonrpc"] == "2.0"
        assert result["result"] == 8
        assert result["id"] == 1

    @pytest.mark.asyncio
    async def test_process_call_with_list_params(self, async_consumer_with_methods):
        """Should handle list parameters in async methods."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_add",
            "params": [10, 20],
            "id": 2,
        }

        result = await async_consumer_with_methods._process_call(
            data, is_notification=False
        )

        assert result["result"] == 30

    @pytest.mark.asyncio
    async def test_process_call_notification_returns_none(
        self, async_consumer_with_methods
    ):
        """Should return None for async notifications."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_notify",
            "params": {"event": "test"},
        }

        result = await async_consumer_with_methods._process_call(
            data, is_notification=True
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_process_call_with_no_params(self, async_consumer_with_methods):
        """Should handle async methods with no params."""

        # Add a method without params
        class TestConsumer(type(async_consumer_with_methods)):  # type: ignore[misc]
            pass

        @TestConsumer.rpc_method()
        async def no_params_method() -> str:
            return "success"

        consumer = TestConsumer(async_consumer_with_methods.scope)
        data = {"jsonrpc": "2.0", "method": "no_params_method", "id": 1}

        result = await consumer._process_call(data, is_notification=False)

        assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_process_call_notification_with_result_logs_warning(
        self, async_consumer_with_methods, caplog
    ):
        """Should log warning when notification returns result."""

        # Create a notification that returns a value (bad practice)
        class TestConsumer(type(async_consumer_with_methods)):  # type: ignore[misc]
            pass

        @TestConsumer.rpc_notification()
        async def bad_notification() -> str:
            return "should not return"

        consumer = TestConsumer(async_consumer_with_methods.scope)
        data = {"jsonrpc": "2.0", "method": "bad_notification"}

        result = await consumer._process_call(data, is_notification=True)

        assert result is None
        assert "notification method shouldn't return any result" in caplog.text


@pytest.mark.unit
class TestAsyncInterceptCall:
    """Test async intercept_call().

    Covers async request/response routing and error handling.
    """

    @pytest.mark.asyncio
    async def test_intercept_call_with_valid_request(self, async_consumer_with_methods):
        """Should process valid async JSON-RPC request."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_add",
            "params": {"a": 1, "b": 2},
            "id": 1,
        }

        result, is_notification = await async_consumer_with_methods._intercept_call(
            data
        )

        assert isinstance(result, dict)
        assert result["result"] == 3
        assert is_notification is False

    @pytest.mark.asyncio
    async def test_intercept_call_with_notification(self, async_consumer_with_methods):
        """Should handle async notification (no response expected)."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_notify",
            "params": {"event": "test"},
        }

        result, is_notification = await async_consumer_with_methods._intercept_call(
            data
        )

        assert result is None
        assert is_notification is True

    @pytest.mark.asyncio
    async def test_intercept_call_with_empty_data(self, mock_async_rpc_consumer):
        """Should return JsonRpcErrorCode.INVALID_REQUEST error for empty data."""
        result, is_notification = await mock_async_rpc_consumer._intercept_call({})

        assert result["jsonrpc"] == "2.0"
        assert result["error"]["code"] == JsonRpcErrorCode.INVALID_REQUEST
        assert is_notification is False

    @pytest.mark.asyncio
    async def test_intercept_call_with_none_data(self, mock_async_rpc_consumer):
        """Should return JsonRpcErrorCode.INVALID_REQUEST error for None data."""
        result, is_notification = await mock_async_rpc_consumer._intercept_call(None)

        assert result["error"]["code"] == JsonRpcErrorCode.INVALID_REQUEST
        assert is_notification is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("invalid_data", [[], "string", 123, True])
    async def test_intercept_call_with_invalid_type(
        self, mock_async_rpc_consumer, invalid_data
    ):
        """Should return JsonRpcErrorCode.INVALID_REQUEST for non-dict data."""
        result, is_notification = await mock_async_rpc_consumer._intercept_call(
            invalid_data
        )

        assert result["error"]["code"] == JsonRpcErrorCode.INVALID_REQUEST
        assert is_notification is False

    @pytest.mark.asyncio
    async def test_intercept_call_detects_response(self, mock_async_rpc_consumer):
        """Should detect JSON-RPC response (has 'result' or 'error' field)."""
        response_data = {"jsonrpc": "2.0", "result": "success", "id": 1}

        result, is_notification = await mock_async_rpc_consumer._intercept_call(
            response_data
        )

        assert result == response_data
        assert is_notification is True  # Response doesn't expect reply

    @pytest.mark.asyncio
    async def test_intercept_call_detects_error_response(self, mock_async_rpc_consumer):
        """Should detect error response."""
        error_data = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request"},
            "id": 1,
        }

        result, is_notification = await mock_async_rpc_consumer._intercept_call(
            error_data
        )

        assert result == error_data
        assert is_notification is True

    @pytest.mark.asyncio
    async def test_intercept_call_catches_jsonrpc_error(
        self, async_consumer_with_methods
    ):
        """Should convert JsonRpcError to error response."""
        data = {
            "jsonrpc": "2.0",
            "method": "unknown_method",
            "id": 1,
        }

        result, is_notification = await async_consumer_with_methods._intercept_call(
            data
        )

        assert "error" in result
        assert result["error"]["code"] == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert result["id"] == 1
        assert is_notification is False

    @pytest.mark.asyncio
    async def test_intercept_call_catches_generic_exception(self):
        """Should convert generic exceptions to GENERIC_APPLICATION_ERROR.

        Security: should not leak internal details.
        """

        class FailingAsyncConsumer(AsyncRpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @FailingAsyncConsumer.rpc_method()
        async def failing_method():
            msg = "Something went wrong"
            raise ValueError(msg)

        consumer = FailingAsyncConsumer()
        data = {"jsonrpc": "2.0", "method": "failing_method", "id": 1}

        result, is_notification = await consumer._intercept_call(data)

        assert "error" in result
        assert result["error"]["code"] == JsonRpcErrorCode.GENERIC_APPLICATION_ERROR
        # Security fix: error message should not leak internal details
        assert result["error"]["message"] == "Application error occurred"
        assert "data" not in result["error"] or result["error"]["data"] is None
        assert result["id"] == 1
        assert is_notification is False

    @pytest.mark.asyncio
    async def test_intercept_call_with_notification_id_none(
        self, async_consumer_with_methods
    ):
        """Should treat missing 'id' as notification."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_notify",
            "params": {"event": "test"},
        }

        _, is_notification = await async_consumer_with_methods._intercept_call(data)

        assert is_notification is True

    @pytest.mark.asyncio
    async def test_intercept_call_with_method_id_present(
        self, async_consumer_with_methods
    ):
        """Should treat request with 'id' as method call."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_add",
            "params": {"a": 1, "b": 2},
            "id": 1,
        }

        _, is_notification = await async_consumer_with_methods._intercept_call(data)

        assert is_notification is False

    @pytest.mark.asyncio
    async def test_intercept_call_exception_with_args(self):
        """Should not leak exception args in error data (security fix)."""

        class FailingAsyncConsumer(AsyncRpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @FailingAsyncConsumer.rpc_method()
        async def method_with_args():
            msg = "Error message"
            raise ValueError(msg)

        consumer = FailingAsyncConsumer()
        data = {"jsonrpc": "2.0", "method": "method_with_args", "id": 1}

        result, _ = await consumer._intercept_call(data)

        # Security fix: exception details should not be leaked
        # data field is not included when None
        assert "data" not in result["error"] or result["error"]["data"] is None

    @pytest.mark.asyncio
    async def test_intercept_call_exception_with_multiple_args(self):
        """Should not leak exception args even with multiple (security fix)."""

        class FailingAsyncConsumer(AsyncRpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @FailingAsyncConsumer.rpc_method()
        async def method_with_multiple_args():
            msg = "Error"
            raise ValueError(msg, 123, {"key": "value"})

        consumer = FailingAsyncConsumer()
        data = {"jsonrpc": "2.0", "method": "method_with_multiple_args", "id": 1}

        result, _ = await consumer._intercept_call(data)

        # Security fix: exception details should not be leaked
        # data field is not included when None
        assert "data" not in result["error"] or result["error"]["data"] is None


@pytest.mark.unit
class TestAsyncBaseReceiveJson:
    """Test async _base_receive_json().

    Covers async message reception and response handling.
    """

    @pytest.mark.asyncio
    async def test_base_receive_json_sends_response_for_method(
        self, async_consumer_with_methods
    ):
        """Should send JSON response for async method calls."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_add",
            "params": {"a": 1, "b": 2},
            "id": 1,
        }

        await async_consumer_with_methods._base_receive_json(data)

        assert len(async_consumer_with_methods.sent_messages) == 1
        response = async_consumer_with_methods.sent_messages[0]
        assert response["result"] == 3

    @pytest.mark.asyncio
    async def test_base_receive_json_no_send_for_notification(
        self, async_consumer_with_methods
    ):
        """Should not send response for async notifications."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_notify",
            "params": {"event": "test"},
        }

        await async_consumer_with_methods._base_receive_json(data)

        assert len(async_consumer_with_methods.sent_messages) == 0

    @pytest.mark.asyncio
    async def test_base_receive_json_sends_error_response(
        self, async_consumer_with_methods
    ):
        """Should send error response for invalid requests."""
        data = {"jsonrpc": "2.0", "method": "unknown_method", "id": 1}

        await async_consumer_with_methods._base_receive_json(data)

        assert len(async_consumer_with_methods.sent_messages) == 1
        response = async_consumer_with_methods.sent_messages[0]
        assert "error" in response
        assert response["error"]["code"] == JsonRpcErrorCode.METHOD_NOT_FOUND

    @pytest.mark.asyncio
    async def test_base_receive_json_no_send_for_response(
        self, mock_async_rpc_consumer
    ):
        """Should not send response when receiving a response."""
        response_data = {"jsonrpc": "2.0", "result": "success", "id": 1}

        await mock_async_rpc_consumer._base_receive_json(response_data)

        assert len(mock_async_rpc_consumer.sent_messages) == 0


@pytest.mark.unit
class TestAsyncProcessingEdgeCases:
    """Test edge cases in async RPC processing."""

    @pytest.mark.asyncio
    async def test_process_call_with_method_returning_none(self):
        """Should handle async methods that return None."""

        class TestAsyncConsumer(AsyncRpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @TestAsyncConsumer.rpc_method()
        async def returns_none():
            return None

        consumer = TestAsyncConsumer()
        data = {"jsonrpc": "2.0", "method": "returns_none", "id": 1}

        result = await consumer._process_call(data, is_notification=False)

        assert isinstance(result, dict)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["result"] is None

    @pytest.mark.asyncio
    async def test_process_call_with_method_returning_false(self):
        """Should handle async methods that return False."""

        class TestAsyncConsumer(AsyncRpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @TestAsyncConsumer.rpc_method()
        async def returns_false():
            return False

        consumer = TestAsyncConsumer()
        data = {"jsonrpc": "2.0", "method": "returns_false", "id": 1}

        result = await consumer._process_call(data, is_notification=False)

        assert result is not None
        assert result["result"] is False

    @pytest.mark.asyncio
    async def test_process_call_with_method_returning_zero(self):
        """Should handle async methods that return 0."""

        class TestAsyncConsumer(AsyncRpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @TestAsyncConsumer.rpc_method()
        async def returns_zero():
            return 0

        consumer = TestAsyncConsumer()
        data = {"jsonrpc": "2.0", "method": "returns_zero", "id": 1}

        result = await consumer._process_call(data, is_notification=False)

        assert result is not None
        assert result["result"] == 0

    @pytest.mark.asyncio
    async def test_intercept_empty_dict_has_correct_rpc_id(
        self, mock_async_rpc_consumer
    ):
        """Should use None rpc_id for empty dict."""
        result, _ = await mock_async_rpc_consumer._intercept_call({})

        # Empty dict has no id field, so rpc_id should be None
        assert result["id"] is None

    @pytest.mark.asyncio
    async def test_intercept_invalid_type_has_none_rpc_id(
        self, mock_async_rpc_consumer
    ):
        """Should use None rpc_id for invalid types."""
        result, _ = await mock_async_rpc_consumer._intercept_call("invalid")

        assert result["id"] is None

    @pytest.mark.asyncio
    async def test_process_call_compressed_flag_always_false(
        self, async_consumer_with_methods
    ):
        """Should always set compressed=False in response."""
        data = {
            "jsonrpc": "2.0",
            "method": "async_add",
            "params": {"a": 1, "b": 1},
            "id": 1,
        }

        result = await async_consumer_with_methods._process_call(
            data, is_notification=False
        )

        # compressed field is only included if True
        assert "compressed" not in result
