"""Quick test to verify middleware functionality works correctly."""

import os

import django
from django.conf import settings

# Configure Django settings before importing channels_rpc
if not settings.configured:
    settings.configure(
        DEBUG=True,
        SECRET_KEY="test-secret-key",
        INSTALLED_APPS=[
            "channels",
            "channels_rpc",
        ],
    )
    django.setup()

from channels_rpc import (
    AsyncJsonRpcWebsocketConsumer,
    JsonRpcError,
    JsonRpcErrorCode,
)
from channels_rpc.middleware import RpcMiddleware


class RateLimitMiddleware:
    """Example middleware for rate limiting."""

    def __init__(self):
        self.call_counts = {}

    def process_request(self, data, consumer):
        method = data.get("method")
        count = self.call_counts.get(method, 0)
        if count > 5:
            raise JsonRpcError(
                data.get("id"),
                JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
                data={"error": "Rate limit exceeded"},
            )
        self.call_counts[method] = count + 1
        return data

    def process_response(self, response, consumer):
        # Add server metadata
        if "result" in response:
            response["_metadata"] = {"server": "test-server"}
        return response


class TestConsumer(AsyncJsonRpcWebsocketConsumer):
    """Test consumer with middleware."""

    middleware = [RateLimitMiddleware()]

    @AsyncJsonRpcWebsocketConsumer.rpc_method()
    async def test_method(self, value: int):
        """Test RPC method."""
        return {"result": value * 2}


def test_middleware_integration():
    """Test that middleware can be imported and used."""
    from channels_rpc.middleware import LoggingMiddleware

    # Test that middleware protocol exists
    assert RpcMiddleware is not None

    # Test that LoggingMiddleware exists
    logger = LoggingMiddleware()
    assert logger is not None

    # Test that consumer has middleware attribute
    consumer = TestConsumer()
    assert hasattr(consumer, "middleware")
    assert len(consumer.middleware) == 1
    assert isinstance(consumer.middleware[0], RateLimitMiddleware)

    print("✓ Middleware protocol and classes are properly defined")
    print("✓ Consumer middleware attribute is accessible")
    print("✓ All middleware integration tests passed!")


if __name__ == "__main__":
    test_middleware_integration()
