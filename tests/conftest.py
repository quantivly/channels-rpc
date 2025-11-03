"""Shared test fixtures for channels-rpc test suite."""

from __future__ import annotations

import os

# Configure Django settings before any Django imports
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

django.setup()

import pytest
from channels.testing import WebsocketCommunicator

from channels_rpc.async_rpc_base import AsyncRpcBase
from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
)
from channels_rpc.rpc_base import RpcBase

# ============================================================================
# Error Code Fixtures
# ============================================================================


@pytest.fixture(
    params=[
        PARSE_ERROR,
        INVALID_REQUEST,
        METHOD_NOT_FOUND,
        INVALID_PARAMS,
        INTERNAL_ERROR,
        GENERIC_APPLICATION_ERROR,
    ]
)
def error_code(request):
    """Parametrized fixture for all RPC error codes."""
    return request.param


@pytest.fixture(params=["1.0", "3.0", "2", 2, 2.0, None, ""])
def invalid_jsonrpc_version(request):
    """Parametrized fixture for invalid JSON-RPC versions."""
    return request.param


@pytest.fixture(params=[123, 45.6, [], {}, None, True, False])
def invalid_method_type(request):
    """Parametrized fixture for invalid method types."""
    return request.param


@pytest.fixture(params=["string", 123, 45.6, True, None])
def invalid_params_type(request):
    """Parametrized fixture for invalid parameter types."""
    return request.param


@pytest.fixture(params=[None, [], "", 123, 45.6, True, False])
def invalid_message_data(request):
    """Parametrized fixture for invalid message data."""
    return request.param


# ============================================================================
# Scope Fixtures
# ============================================================================


@pytest.fixture
def mock_websocket_scope():
    """Mock Django Channels scope for WebSocket."""
    return {
        "type": "websocket",
        "path": "/ws/",
        "headers": [],
        "query_string": b"",
    }


@pytest.fixture
def mock_http_scope():
    """Mock Django Channels scope for HTTP."""
    return {
        "type": "http",
        "method": "POST",
        "path": "/rpc/",
        "headers": [],
        "query_string": b"",
    }


# ============================================================================
# Mock Consumer Classes
# ============================================================================


class MockRpcConsumer(RpcBase):
    """Mock synchronous RPC consumer for testing."""

    def __init__(self, scope=None):
        self.scope = scope or {"type": "websocket"}
        self.sent_messages = []

    def send_json(self, data):
        """Mock send_json to capture sent messages."""
        self.sent_messages.append(data)

    def send(self, data):
        """Mock send for text messages."""
        self.sent_messages.append(data)

    def encode_json(self, data):
        """Mock JSON encoding."""
        import json

        return json.dumps(data)


class MockAsyncRpcConsumer(AsyncRpcBase):
    """Mock asynchronous RPC consumer for testing."""

    def __init__(self, scope=None):
        self.scope = scope or {"type": "websocket"}
        self.sent_messages = []

    async def send_json(self, data):
        """Mock send_json to capture sent messages."""
        self.sent_messages.append(data)

    async def send(self, data):
        """Mock send for text messages."""
        self.sent_messages.append(data)

    def encode_json(self, data):
        """Mock JSON encoding."""
        import json

        return json.dumps(data)


# ============================================================================
# Consumer Instance Fixtures
# ============================================================================


@pytest.fixture
def mock_rpc_consumer(mock_websocket_scope):
    """Fixture providing a mock RPC consumer."""
    return MockRpcConsumer(mock_websocket_scope)


@pytest.fixture
def mock_async_rpc_consumer(mock_websocket_scope):
    """Fixture providing a mock async RPC consumer."""
    return MockAsyncRpcConsumer(mock_websocket_scope)


# ============================================================================
# Consumers with Registered Methods
# ============================================================================


@pytest.fixture
def consumer_with_methods(mock_websocket_scope):
    """Consumer with registered test methods."""

    class TestConsumer(MockRpcConsumer):
        pass

    @TestConsumer.rpc_method()
    def add(a: int, b: int) -> int:
        return a + b

    @TestConsumer.rpc_method()
    def echo(message: str, **kwargs) -> str:
        consumer = kwargs.get("consumer")
        return f"Echo: {message} (consumer: {consumer is not None})"

    @TestConsumer.rpc_method(websocket=True, http=False)
    def websocket_only() -> str:
        return "websocket"

    @TestConsumer.rpc_method(http=True, websocket=False)
    def http_only() -> str:
        return "http"

    @TestConsumer.rpc_notification()
    def notify_event(event: str) -> None:
        pass

    return TestConsumer(mock_websocket_scope)


@pytest.fixture
def async_consumer_with_methods(mock_websocket_scope):
    """Async consumer with registered test methods."""

    class TestAsyncConsumer(MockAsyncRpcConsumer):
        pass

    @TestAsyncConsumer.rpc_method()
    async def async_add(a: int, b: int) -> int:
        return a + b

    @TestAsyncConsumer.rpc_method()
    async def async_echo(message: str, **kwargs) -> str:
        consumer = kwargs.get("consumer")
        return f"Echo: {message} (consumer: {consumer is not None})"

    @TestAsyncConsumer.rpc_notification()
    async def async_notify(event: str) -> None:
        pass

    return TestAsyncConsumer(mock_websocket_scope)


# ============================================================================
# JSON-RPC Message Fixtures
# ============================================================================


@pytest.fixture
def valid_request():
    """Valid JSON-RPC 2.0 request."""
    return {
        "jsonrpc": "2.0",
        "method": "test_method",
        "params": {"arg": "value"},
        "id": 1,
    }


@pytest.fixture
def valid_request_with_list_params():
    """Valid JSON-RPC 2.0 request with list parameters."""
    return {
        "jsonrpc": "2.0",
        "method": "test_method",
        "params": [1, 2, 3],
        "id": 2,
    }


@pytest.fixture
def valid_notification():
    """Valid JSON-RPC 2.0 notification (no id)."""
    return {
        "jsonrpc": "2.0",
        "method": "test_notification",
        "params": {"event": "test"},
    }


@pytest.fixture
def valid_response():
    """Valid JSON-RPC 2.0 response."""
    return {
        "jsonrpc": "2.0",
        "result": "success",
        "id": 1,
    }


@pytest.fixture
def error_response():
    """Valid JSON-RPC 2.0 error response."""
    return {
        "jsonrpc": "2.0",
        "error": {
            "code": -32600,
            "message": "Invalid Request",
        },
        "id": 1,
    }


# ============================================================================
# WebSocket Testing Fixtures
# ============================================================================


@pytest.fixture
def websocket_communicator_factory():
    """Factory fixture for WebSocket communicators."""

    def _make_communicator(consumer_class, path="/ws/"):
        return WebsocketCommunicator(consumer_class.as_asgi(), path)

    return _make_communicator
