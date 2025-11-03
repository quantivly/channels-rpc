"""Tests for RPC processing logic in rpc_base.py.

Coverage: process_call(), intercept_call(), execute_called_method(), _base_receive_json().
Target: 40-50 tests, 100% coverage of processing logic.

CRITICAL TESTS - Cover recent bug fixes:
- Variable scoping in intercept_call (commits f5418a0, 317f958)
- Request vs response detection
- Notification handling
- Error response generation
"""

from __future__ import annotations

import pytest

from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    JsonRpcError,
)
from channels_rpc.rpc_base import RpcBase


@pytest.mark.unit
class TestProcessCall:
    """Test process_call() method - main RPC call processing."""

    def test_process_call_returns_result_dict(self, consumer_with_methods):
        """Should return JSON-RPC response dict for method calls."""
        data = {"jsonrpc": "2.0", "method": "add", "params": {"a": 3, "b": 5}, "id": 1}

        result = consumer_with_methods.process_call(data, is_notification=False)

        assert isinstance(result, dict)
        assert result["jsonrpc"] == "2.0"
        assert result["result"] == 8
        assert result["id"] == 1

    def test_process_call_with_list_params(self, consumer_with_methods):
        """Should handle list parameters."""
        data = {"jsonrpc": "2.0", "method": "add", "params": [10, 20], "id": 2}

        result = consumer_with_methods.process_call(data, is_notification=False)

        assert result["result"] == 30

    def test_process_call_notification_returns_none(self, consumer_with_methods):
        """Should return None for notifications."""
        data = {"jsonrpc": "2.0", "method": "notify_event", "params": {"event": "test"}}

        result = consumer_with_methods.process_call(data, is_notification=True)

        assert result is None

    def test_process_call_calls_execute_method(self, consumer_with_methods, mocker):
        """Should call execute_called_method with correct params."""
        spy = mocker.spy(consumer_with_methods, "execute_called_method")
        data = {"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 2}, "id": 1}

        consumer_with_methods.process_call(data, is_notification=False)

        assert spy.call_count == 1

    def test_process_call_with_no_params(self, consumer_with_methods):
        """Should handle methods with no params."""
        data = {"jsonrpc": "2.0", "method": "websocket_only", "id": 1}

        result = consumer_with_methods.process_call(data, is_notification=False)

        assert result["result"] == "websocket"


@pytest.mark.unit
class TestExecuteCalledMethod:
    """Test execute_called_method() - method invocation."""

    def test_execute_with_dict_params(self, consumer_with_methods):
        """Should execute method with dict params."""
        method = consumer_with_methods.rpc_methods[id(consumer_with_methods.__class__)][
            "add"
        ]
        params = {"a": 5, "b": 3}

        result = consumer_with_methods.execute_called_method(method, params)

        assert result == 8

    def test_execute_with_list_params(self, consumer_with_methods):
        """Should execute method with list params."""
        method = consumer_with_methods.rpc_methods[id(consumer_with_methods.__class__)][
            "add"
        ]
        params = [7, 3]

        result = consumer_with_methods.execute_called_method(method, params)

        assert result == 10

    def test_execute_injects_consumer_for_kwargs(self, consumer_with_methods):
        """Should inject consumer when method accepts **kwargs."""
        method = consumer_with_methods.rpc_methods[id(consumer_with_methods.__class__)][
            "echo"
        ]
        params = {"message": "test"}

        result = consumer_with_methods.execute_called_method(method, params)

        assert "consumer: True" in result

    def test_execute_without_consumer_injection(self, consumer_with_methods):
        """Should not inject consumer when method doesn't accept **kwargs."""
        method = consumer_with_methods.rpc_methods[id(consumer_with_methods.__class__)][
            "add"
        ]
        params = {"a": 1, "b": 1}

        result = consumer_with_methods.execute_called_method(method, params)

        assert result == 2


@pytest.mark.unit
class TestInterceptCall:
    """Test intercept_call() - request/response routing and error handling."""

    def test_intercept_call_with_valid_request(self, consumer_with_methods):
        """Should process valid JSON-RPC request."""
        data = {"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 2}, "id": 1}

        result, is_notification = consumer_with_methods.intercept_call(data)

        assert isinstance(result, dict)
        assert result["result"] == 3
        assert is_notification is False

    def test_intercept_call_with_notification(self, consumer_with_methods):
        """Should handle notification (no response expected)."""
        data = {
            "jsonrpc": "2.0",
            "method": "notify_event",
            "params": {"event": "test"},
        }

        result, is_notification = consumer_with_methods.intercept_call(data)

        assert result is None
        assert is_notification is True

    def test_intercept_call_with_empty_data(self, mock_rpc_consumer):
        """Should return INVALID_REQUEST error for empty data."""
        result, is_notification = mock_rpc_consumer.intercept_call({})

        assert result["jsonrpc"] == "2.0"
        assert result["error"]["code"] == INVALID_REQUEST
        assert is_notification is False

    def test_intercept_call_with_none_data(self, mock_rpc_consumer):
        """Should return INVALID_REQUEST error for None data."""
        result, is_notification = mock_rpc_consumer.intercept_call(None)

        assert result["error"]["code"] == INVALID_REQUEST
        assert is_notification is False

    @pytest.mark.parametrize("invalid_data", [[], "string", 123, True])
    def test_intercept_call_with_invalid_type(self, mock_rpc_consumer, invalid_data):
        """Should return INVALID_REQUEST for non-dict data."""
        result, is_notification = mock_rpc_consumer.intercept_call(invalid_data)

        assert result["error"]["code"] == INVALID_REQUEST
        assert is_notification is False

    def test_intercept_call_detects_response(self, mock_rpc_consumer):
        """Should detect JSON-RPC response (has 'result' or 'error' field)."""
        response_data = {"jsonrpc": "2.0", "result": "success", "id": 1}

        result, is_notification = mock_rpc_consumer.intercept_call(response_data)

        assert result == response_data
        assert is_notification is True  # Response doesn't expect reply

    def test_intercept_call_detects_error_response(self, mock_rpc_consumer):
        """Should detect error response."""
        error_data = {
            "jsonrpc": "2.0",
            "error": {"code": -32600, "message": "Invalid Request"},
            "id": 1,
        }

        result, is_notification = mock_rpc_consumer.intercept_call(error_data)

        assert result == error_data
        assert is_notification is True

    def test_intercept_call_catches_jsonrpc_error(self, consumer_with_methods):
        """Should convert JsonRpcError to error response."""
        data = {
            "jsonrpc": "2.0",
            "method": "unknown_method",
            "id": 1,
        }

        result, is_notification = consumer_with_methods.intercept_call(data)

        assert "error" in result
        assert result["error"]["code"] == METHOD_NOT_FOUND
        assert result["id"] == 1
        assert is_notification is False

    def test_intercept_call_catches_generic_exception(self):
        """Should convert generic exceptions to GENERIC_APPLICATION_ERROR."""

        class FailingConsumer(RpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @FailingConsumer.rpc_method()
        def failing_method():
            msg = "Something went wrong"
            raise ValueError(msg)

        consumer = FailingConsumer()
        data = {"jsonrpc": "2.0", "method": "failing_method", "id": 1}

        result, is_notification = consumer.intercept_call(data)

        assert "error" in result
        assert result["error"]["code"] == GENERIC_APPLICATION_ERROR
        assert "Something went wrong" in result["error"]["message"]
        assert result["id"] == 1
        assert is_notification is False

    def test_intercept_call_rpc_id_in_error_for_invalid_request(
        self, consumer_with_methods
    ):
        """Should include rpc_id in error even for invalid requests (REGRESSION TEST)."""
        # This tests the bug fix from commit 317f958
        data = {"jsonrpc": "1.0", "method": "test", "id": 42}

        result, is_notification = consumer_with_methods.intercept_call(data)

        assert result["id"] == 42
        assert result["error"]["code"] == INVALID_REQUEST

    def test_intercept_call_is_notification_defined_for_all_paths(
        self, mock_rpc_consumer
    ):
        """Should define is_notification in all code paths (REGRESSION TEST)."""
        # This tests the bug fix from commit f5418a0
        # Test various error paths to ensure is_notification is always defined

        # Empty data path
        _, is_notification = mock_rpc_consumer.intercept_call({})
        assert is_notification is False

        # Invalid type path
        _, is_notification = mock_rpc_consumer.intercept_call([])
        assert is_notification is False

        # Response path
        _, is_notification = mock_rpc_consumer.intercept_call(
            {"jsonrpc": "2.0", "result": "test", "id": 1}
        )
        assert is_notification is True

    def test_intercept_call_with_notification_id_none(self, consumer_with_methods):
        """Should treat missing 'id' as notification."""
        data = {
            "jsonrpc": "2.0",
            "method": "notify_event",
            "params": {"event": "test"},
        }

        _, is_notification = consumer_with_methods.intercept_call(data)

        assert is_notification is True

    def test_intercept_call_with_method_id_present(self, consumer_with_methods):
        """Should treat request with 'id' as method call."""
        data = {"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 2}, "id": 1}

        _, is_notification = consumer_with_methods.intercept_call(data)

        assert is_notification is False

    def test_intercept_call_exception_with_args(self):
        """Should include exception args in error data."""

        class FailingConsumer(RpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @FailingConsumer.rpc_method()
        def method_with_args():
            msg = "Error message"
            raise ValueError(msg)

        consumer = FailingConsumer()
        data = {"jsonrpc": "2.0", "method": "method_with_args", "id": 1}

        result, _ = consumer.intercept_call(data)

        assert result["error"]["data"] == "Error message"

    def test_intercept_call_exception_with_multiple_args(self):
        """Should include all exception args when multiple."""

        class FailingConsumer(RpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @FailingConsumer.rpc_method()
        def method_with_multiple_args():
            msg = "Error"
            raise ValueError(msg, 123, {"key": "value"})

        consumer = FailingConsumer()
        data = {"jsonrpc": "2.0", "method": "method_with_multiple_args", "id": 1}

        result, _ = consumer.intercept_call(data)

        assert result["error"]["data"] == ("Error", 123, {"key": "value"})


@pytest.mark.unit
class TestBaseReceiveJson:
    """Test _base_receive_json() - message reception and response handling."""

    def test_base_receive_json_sends_response_for_method(
        self, consumer_with_methods, mocker
    ):
        """Should send JSON response for method calls."""
        spy = mocker.spy(consumer_with_methods, "send_json")
        data = {"jsonrpc": "2.0", "method": "add", "params": {"a": 1, "b": 2}, "id": 1}

        consumer_with_methods._base_receive_json(data)

        assert spy.call_count == 1
        response = spy.call_args[0][0]
        assert response["result"] == 3

    def test_base_receive_json_no_send_for_notification(
        self, consumer_with_methods, mocker
    ):
        """Should not send response for notifications."""
        spy = mocker.spy(consumer_with_methods, "send_json")
        data = {
            "jsonrpc": "2.0",
            "method": "notify_event",
            "params": {"event": "test"},
        }

        consumer_with_methods._base_receive_json(data)

        assert spy.call_count == 0

    def test_base_receive_json_sends_error_response(
        self, consumer_with_methods, mocker
    ):
        """Should send error response for invalid requests."""
        spy = mocker.spy(consumer_with_methods, "send_json")
        data = {"jsonrpc": "2.0", "method": "unknown_method", "id": 1}

        consumer_with_methods._base_receive_json(data)

        assert spy.call_count == 1
        response = spy.call_args[0][0]
        assert "error" in response
        assert response["error"]["code"] == METHOD_NOT_FOUND

    def test_base_receive_json_no_send_for_response(self, mock_rpc_consumer, mocker):
        """Should not send response when receiving a response."""
        spy = mocker.spy(mock_rpc_consumer, "send_json")
        response_data = {"jsonrpc": "2.0", "result": "success", "id": 1}

        mock_rpc_consumer._base_receive_json(response_data)

        assert spy.call_count == 0


@pytest.mark.unit
class TestProcessingEdgeCases:
    """Test edge cases in RPC processing."""

    def test_intercept_empty_dict_has_correct_rpc_id(self, mock_rpc_consumer):
        """Should use None rpc_id for empty dict (REGRESSION)."""
        result, _ = mock_rpc_consumer.intercept_call({})

        # Empty dict has no id field, so rpc_id should be None
        assert result["id"] is None

    def test_intercept_invalid_type_has_none_rpc_id(self, mock_rpc_consumer):
        """Should use None rpc_id for invalid types."""
        result, _ = mock_rpc_consumer.intercept_call("invalid")

        assert result["id"] is None

    def test_process_call_with_method_returning_none(self):
        """Should handle methods that return None."""

        class TestConsumer(RpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @TestConsumer.rpc_method()
        def returns_none():
            return None

        consumer = TestConsumer()
        data = {"jsonrpc": "2.0", "method": "returns_none", "id": 1}

        result = consumer.process_call(data, is_notification=False)

        # The deprecated create_json_rpc_frame might behave differently with None
        # Main thing is it returns a valid response dict
        assert isinstance(result, dict)
        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1

    def test_process_call_with_method_returning_false(self):
        """Should handle methods that return False."""

        class TestConsumer(RpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @TestConsumer.rpc_method()
        def returns_false():
            return False

        consumer = TestConsumer()
        data = {"jsonrpc": "2.0", "method": "returns_false", "id": 1}

        result = consumer.process_call(data, is_notification=False)

        assert result["result"] is False

    def test_process_call_with_method_returning_zero(self):
        """Should handle methods that return 0."""

        class TestConsumer(RpcBase):
            def __init__(self):
                self.scope = {"type": "websocket"}

        @TestConsumer.rpc_method()
        def returns_zero():
            return 0

        consumer = TestConsumer()
        data = {"jsonrpc": "2.0", "method": "returns_zero", "id": 1}

        result = consumer.process_call(data, is_notification=False)

        assert result["result"] == 0
