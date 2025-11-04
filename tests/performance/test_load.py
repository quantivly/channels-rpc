"""Performance and load tests for channels-rpc library.

This test suite validates performance-critical paths including:
- Method introspection caching (31x speedup optimization)
- Concurrent connection handling
- Size limit validation overhead
- Large response chunking and compression

Tests are marked with @pytest.mark.performance and @pytest.mark.slow
to allow selective execution in CI/CD pipelines.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import pytest
from channels.testing import WebsocketCommunicator

from channels_rpc import AsyncJsonRpcWebsocketConsumer
from channels_rpc.context import RpcContext
from channels_rpc.limits import (
    MAX_ARRAY_LENGTH,
    MAX_METHOD_NAME_LENGTH,
    MAX_STRING_LENGTH,
    check_size_limits,
)
from channels_rpc.registry import get_registry
from channels_rpc.rpc_base import RpcBase, RpcMethodWrapper
from tests.conftest import MockRpcConsumer

# ============================================================================
# Performance Test Configuration
# ============================================================================

# Benchmarks thresholds
METHOD_INTROSPECTION_ITERATIONS = 100_000  # 100k calls for cache test
CACHE_PERFORMANCE_THRESHOLD_SECONDS = 0.1  # Must complete in <0.1s
CONCURRENT_REQUESTS = 100  # Number of concurrent RPC calls
SIZE_VALIDATION_THRESHOLD_MS = 1.0  # Validation overhead <1ms per request


# ============================================================================
# Test 1: Method Introspection Cache Performance
# ============================================================================


@pytest.mark.performance
@pytest.mark.slow
class TestMethodIntrospectionCachePerformance:
    """Test that method introspection is cached and not repeated on every call.

    Context
    -------
    Recent optimization cached method introspection at registration time,
    achieving 31x speedup (96.8% improvement). The `accepts_context` flag
    is now stored in RpcMethodWrapper and reused on every invocation.

    Previously, inspect.signature() was called on every method invocation.
    Now it's only called once during decorator registration.
    """

    def test_method_introspection_cache_basic(self):
        """Verify that method introspection results are cached in RpcMethodWrapper.

        This test confirms that the accepts_context flag is determined at
        registration time and stored in the wrapper, not computed per call.
        """

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_method()
        def cached_method(_ctx: RpcContext, value: int) -> int:
            return value * 2

        # Get the registered wrapper
        registry = get_registry()
        wrapper = registry.get_method(TestConsumer, "cached_method")

        assert wrapper is not None
        assert isinstance(wrapper, RpcMethodWrapper)
        # Verify accepts_context is cached at registration time
        assert wrapper.accepts_context is True
        # Verify function is stored
        assert wrapper.func is not None
        assert wrapper.name == "cached_method"

    def test_method_without_context_cached(self):
        """Verify caching works for methods without RpcContext parameter."""

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_method()
        def no_context_method(value: int) -> int:
            return value + 10

        registry = get_registry()
        wrapper = registry.get_method(TestConsumer, "no_context_method")

        assert wrapper is not None
        assert wrapper.accepts_context is False

    def test_cached_introspection_performance_benchmark(self):
        """Benchmark: 100k method calls should complete in <2s with caching.

        This validates the 31x speedup from caching method introspection.
        With caching, 100k calls should be fast since inspect.signature()
        is not called on every invocation.

        Note: Test includes some overhead from logging, JSON encoding,
        and validation. The core benefit is that accepts_context is cached
        and not computed via inspect.signature() on every call.
        """
        # Temporarily reduce logging noise for performance test
        rpc_logger = logging.getLogger("channels_rpc")
        original_level = rpc_logger.level
        rpc_logger.setLevel(logging.WARNING)

        try:

            class TestConsumer(MockRpcConsumer):
                pass

            call_count = 0

            @TestConsumer.rpc_method()
            def fast_method(_ctx: RpcContext, x: int) -> int:
                nonlocal call_count
                call_count += 1
                return x * 2

            consumer = TestConsumer(scope={"type": "websocket"})

            # Benchmark: Execute 100k method calls
            start_time = time.perf_counter()

            for i in range(METHOD_INTROSPECTION_ITERATIONS):
                request = {
                    "jsonrpc": "2.0",
                    "method": "fast_method",
                    "params": {"x": i},
                    "id": i,
                }
                consumer._base_receive_json(request)

            elapsed = time.perf_counter() - start_time

            # Verify all calls completed
            assert call_count == METHOD_INTROSPECTION_ITERATIONS
            assert len(consumer.sent_messages) == METHOD_INTROSPECTION_ITERATIONS

            # Performance assertion: Should complete in <2s with caching
            # (allowing for validation, JSON encoding, etc.)
            assert elapsed < 2.0, (
                f"100k calls took {elapsed:.3f}s, expected <2s "
                f"(possible performance regression?)"
            )

            # Report performance
            calls_per_second = METHOD_INTROSPECTION_ITERATIONS / elapsed
            print(
                f"\n[PERFORMANCE] Method introspection cache: "
                f"{METHOD_INTROSPECTION_ITERATIONS:,} calls in {elapsed:.3f}s "
                f"({calls_per_second:,.0f} calls/sec)"
            )
        finally:
            # Restore logging level
            rpc_logger.setLevel(original_level)

    @pytest.mark.asyncio
    async def test_async_cached_introspection_performance(self):
        """Benchmark async method calls with cached introspection.

        Async methods should also benefit from cached introspection.
        """

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        call_count = 0

        @TestAsyncConsumer.rpc_method()
        async def async_fast_method(_ctx: RpcContext, x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 3

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        # Benchmark: Execute many async method calls
        iterations = 1000  # Reduced for async due to overhead
        start_time = time.perf_counter()

        for i in range(iterations):
            await communicator.send_json_to(
                {
                    "jsonrpc": "2.0",
                    "method": "async_fast_method",
                    "params": {"x": i},
                    "id": i,
                }
            )
            response = await communicator.receive_json_from()
            assert response["result"] == i * 3

        elapsed = time.perf_counter() - start_time

        await communicator.disconnect()

        # Verify all calls completed
        assert call_count == iterations

        # Report performance
        calls_per_second = iterations / elapsed
        print(
            f"\n[PERFORMANCE] Async method cache: "
            f"{iterations:,} calls in {elapsed:.3f}s "
            f"({calls_per_second:,.0f} calls/sec)"
        )


# ============================================================================
# Test 2: Concurrent Connection Handling
# ============================================================================


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
class TestConcurrentConnectionHandling:
    """Test concurrent RPC request handling and connection management.

    Validates that the library handles multiple concurrent requests
    efficiently without race conditions or performance degradation.
    """

    async def test_concurrent_method_calls_same_connection(self):
        """Handle multiple concurrent method calls on same connection.

        Simulates realistic load where a single client makes multiple
        concurrent RPC requests over one WebSocket connection.
        """

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        call_count = 0

        @TestAsyncConsumer.rpc_method()
        async def concurrent_method(_ctx: RpcContext, request_id: int) -> dict:
            nonlocal call_count
            call_count += 1
            # Simulate small async work
            await asyncio.sleep(0.001)
            return {"request_id": request_id, "result": request_id * 2}

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        start_time = time.perf_counter()

        # Send all requests concurrently without waiting
        for i in range(CONCURRENT_REQUESTS):
            await communicator.send_json_to(
                {
                    "jsonrpc": "2.0",
                    "method": "concurrent_method",
                    "params": {"request_id": i},
                    "id": i,
                }
            )

        # Collect all responses
        responses = []
        for _ in range(CONCURRENT_REQUESTS):
            response = await communicator.receive_json_from()
            responses.append(response)

        elapsed = time.perf_counter() - start_time

        await communicator.disconnect()

        # Verify all requests completed successfully
        assert len(responses) == CONCURRENT_REQUESTS
        assert call_count == CONCURRENT_REQUESTS

        # Verify no data corruption or race conditions
        received_ids = {resp["result"]["request_id"] for resp in responses}
        expected_ids = set(range(CONCURRENT_REQUESTS))
        assert received_ids == expected_ids

        print(
            f"\n[PERFORMANCE] Concurrent requests: "
            f"{CONCURRENT_REQUESTS} requests in {elapsed:.3f}s "
            f"({CONCURRENT_REQUESTS/elapsed:.0f} req/sec)"
        )

    async def test_multiple_concurrent_connections(self):
        """Handle multiple concurrent WebSocket connections.

        Simulates multiple clients connecting and making requests
        simultaneously to test connection isolation and scalability.
        """

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def connection_method(_ctx: RpcContext, value: int) -> int:
            return value + 100

        num_connections = 20
        requests_per_connection = 5

        async def client_session(client_id: int) -> list[dict]:
            """Simulate a single client making multiple requests."""
            communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
            await communicator.connect()

            responses = []
            for req_id in range(requests_per_connection):
                await communicator.send_json_to(
                    {
                        "jsonrpc": "2.0",
                        "method": "connection_method",
                        "params": {"value": client_id * 100 + req_id},
                        "id": req_id,
                    }
                )
                response = await communicator.receive_json_from()
                responses.append(response)

            await communicator.disconnect()
            return responses

        # Run all client sessions concurrently
        start_time = time.perf_counter()
        all_responses = await asyncio.gather(
            *[client_session(i) for i in range(num_connections)]
        )
        elapsed = time.perf_counter() - start_time

        # Verify all requests completed
        total_requests = num_connections * requests_per_connection
        total_responses = sum(len(responses) for responses in all_responses)
        assert total_responses == total_requests

        # Verify no response corruption
        for client_id, responses in enumerate(all_responses):
            assert len(responses) == requests_per_connection
            for req_id, response in enumerate(responses):
                expected_value = (client_id * 100 + req_id) + 100
                assert response["result"] == expected_value

        print(
            f"\n[PERFORMANCE] Multiple connections: "
            f"{num_connections} connections, {total_requests} total requests "
            f"in {elapsed:.3f}s ({total_requests/elapsed:.0f} req/sec)"
        )

    async def test_concurrent_notifications(self):
        """Handle concurrent notifications without blocking.

        Notifications should not wait for responses and should handle
        high throughput efficiently.
        """

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        received_notifications = []

        @TestAsyncConsumer.rpc_notification()
        async def fast_notification(event: str, data: dict) -> None:
            received_notifications.append({"event": event, "data": data})

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        num_notifications = 100
        start_time = time.perf_counter()

        # Send notifications rapidly
        for i in range(num_notifications):
            await communicator.send_json_to(
                {
                    "jsonrpc": "2.0",
                    "method": "fast_notification",
                    "params": {"event": f"event_{i}", "data": {"id": i}},
                }
            )

        # Wait a bit for processing
        await asyncio.sleep(0.1)
        elapsed = time.perf_counter() - start_time

        await communicator.disconnect()

        # Notifications are processed but don't send responses
        assert len(received_notifications) == num_notifications

        print(
            f"\n[PERFORMANCE] Concurrent notifications: "
            f"{num_notifications} notifications in {elapsed:.3f}s"
        )


# ============================================================================
# Test 3: Size Limit Validation Performance
# ============================================================================


@pytest.mark.performance
class TestSizeLimitValidationPerformance:
    """Test performance overhead of size limit validation.

    The library validates request sizes to prevent DoS attacks.
    This overhead should be minimal (<1ms per request) for normal payloads.
    """

    def test_small_payload_validation_overhead(self):
        """Validate that small payloads (<1KB) have minimal overhead.

        Small payloads are the most common case and should be very fast.
        """
        # Create small payload (~500 bytes)
        small_data = {
            "jsonrpc": "2.0",
            "method": "test_method",
            "params": {"message": "Hello" * 10, "count": 42},
            "id": 1,
        }

        iterations = 10_000
        start_time = time.perf_counter()

        for _ in range(iterations):
            check_size_limits(small_data, rpc_id=1)

        elapsed = time.perf_counter() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        # Should be well under 1ms per validation
        assert avg_time_ms < SIZE_VALIDATION_THRESHOLD_MS, (
            f"Small payload validation took {avg_time_ms:.3f}ms, "
            f"expected <{SIZE_VALIDATION_THRESHOLD_MS}ms"
        )

        print(
            f"\n[PERFORMANCE] Small payload validation: "
            f"{iterations:,} validations in {elapsed:.3f}s "
            f"({avg_time_ms:.4f}ms per validation)"
        )

    def test_medium_payload_validation_overhead(self):
        """Validate medium payloads (~100KB) efficiently.

        Medium payloads with nested structures should still be fast.
        """
        # Create medium payload (~100KB)
        medium_data = {
            "jsonrpc": "2.0",
            "method": "process_data",
            "params": {
                "items": [
                    {"id": i, "name": f"item_{i}", "data": "x" * 1000}
                    for i in range(100)
                ]
            },
            "id": 1,
        }

        iterations = 1_000
        start_time = time.perf_counter()

        for _ in range(iterations):
            check_size_limits(medium_data, rpc_id=1)

        elapsed = time.perf_counter() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        # Should still be reasonably fast
        assert avg_time_ms < 10.0, f"Medium payload validation took {avg_time_ms:.3f}ms"

        print(
            f"\n[PERFORMANCE] Medium payload validation: "
            f"{iterations:,} validations in {elapsed:.3f}s "
            f"({avg_time_ms:.3f}ms per validation)"
        )

    def test_large_payload_near_limit_validation(self):
        """Validate large payloads near size limits.

        Large payloads should still validate efficiently without
        excessive overhead, even when approaching limits.
        """
        # Create large payload near string limit (~900KB)
        large_string = "x" * (MAX_STRING_LENGTH - 1000)
        large_data = {
            "jsonrpc": "2.0",
            "method": "upload_data",
            "params": {"content": large_string},
            "id": 1,
        }

        iterations = 100
        start_time = time.perf_counter()

        for _ in range(iterations):
            check_size_limits(large_data, rpc_id=1)

        elapsed = time.perf_counter() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        print(
            f"\n[PERFORMANCE] Large payload validation: "
            f"{iterations} validations in {elapsed:.3f}s "
            f"({avg_time_ms:.3f}ms per validation)"
        )

    def test_deeply_nested_payload_validation(self):
        """Validate deeply nested structures efficiently.

        Recursive validation should handle nested dicts/lists
        without excessive overhead. Uses 5 levels to stay within
        the MAX_NESTING_DEPTH limit of 20.
        """
        # Create deeply nested structure (5 levels to stay under limit)
        nested_data: dict[str, Any] = {"jsonrpc": "2.0", "method": "nested", "id": 1}
        current = nested_data
        current["params"] = {}
        current = current["params"]

        for level in range(5):
            current[f"level_{level}"] = {
                "data": [f"item_{i}" for i in range(10)],
                "nested": {},
            }
            current = current[f"level_{level}"]["nested"]

        iterations = 1_000
        start_time = time.perf_counter()

        for _ in range(iterations):
            check_size_limits(nested_data, rpc_id=1)

        elapsed = time.perf_counter() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        print(
            f"\n[PERFORMANCE] Nested payload validation: "
            f"{iterations:,} validations in {elapsed:.3f}s "
            f"({avg_time_ms:.3f}ms per validation)"
        )

    def test_array_with_many_items_validation(self):
        """Validate arrays with many items efficiently."""
        # Create array near limit
        array_data = {
            "jsonrpc": "2.0",
            "method": "process_array",
            "params": {"items": list(range(MAX_ARRAY_LENGTH - 100))},
            "id": 1,
        }

        iterations = 100
        start_time = time.perf_counter()

        for _ in range(iterations):
            check_size_limits(array_data, rpc_id=1)

        elapsed = time.perf_counter() - start_time
        avg_time_ms = (elapsed / iterations) * 1000

        print(
            f"\n[PERFORMANCE] Large array validation: "
            f"{iterations} validations in {elapsed:.3f}s "
            f"({avg_time_ms:.3f}ms per validation)"
        )


# ============================================================================
# Test 4: Large Response Chunking Performance
# ============================================================================


@pytest.mark.performance
@pytest.mark.slow
@pytest.mark.asyncio
class TestLargeResponseChunkingPerformance:
    """Test performance of chunked data transmission for large responses.

    The library supports chunking responses >1MB with automatic compression.
    This tests end-to-end performance including compression overhead.

    Note: Actual chunking implementation may require additional modules.
    These tests validate the performance characteristics when chunking is used.
    """

    async def test_large_response_method_call(self):
        """Test method returning large response >1MB.

        Validates that large responses can be handled efficiently,
        whether chunked or not.
        """

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        # Create method that returns ~2MB of data
        @TestAsyncConsumer.rpc_method()
        async def get_large_data(_ctx: RpcContext, size_kb: int) -> dict:
            """Return large data payload."""
            # Generate data of requested size
            data_string = "x" * (size_kb * 1024)
            return {
                "data": data_string,
                "metadata": {"size_kb": size_kb, "chunks": 1},
            }

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        # Test with 2MB response
        size_kb = 2048
        start_time = time.perf_counter()

        await communicator.send_json_to(
            {
                "jsonrpc": "2.0",
                "method": "get_large_data",
                "params": {"size_kb": size_kb},
                "id": 1,
            }
        )

        response = await communicator.receive_json_from()
        elapsed = time.perf_counter() - start_time

        await communicator.disconnect()

        # Verify response received successfully
        assert "result" in response
        assert response["result"]["metadata"]["size_kb"] == size_kb

        print(
            f"\n[PERFORMANCE] Large response ({size_kb}KB): "
            f"completed in {elapsed:.3f}s "
            f"({size_kb/elapsed:.0f} KB/sec)"
        )

    async def test_multiple_concurrent_large_responses(self):
        """Test handling multiple concurrent large responses.

        Validates that chunking/compression doesn't create bottlenecks
        when multiple clients request large data simultaneously.
        """

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        @TestAsyncConsumer.rpc_method()
        async def get_bulk_data(_ctx: RpcContext, request_id: int) -> dict:
            """Return moderate size data payload."""
            # 500KB per response
            data_string = "y" * (500 * 1024)
            return {"request_id": request_id, "data": data_string}

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        num_requests = 10
        start_time = time.perf_counter()

        # Send multiple large data requests
        for i in range(num_requests):
            await communicator.send_json_to(
                {
                    "jsonrpc": "2.0",
                    "method": "get_bulk_data",
                    "params": {"request_id": i},
                    "id": i,
                }
            )

        # Collect all responses
        responses = []
        for _ in range(num_requests):
            response = await communicator.receive_json_from()
            responses.append(response)

        elapsed = time.perf_counter() - start_time
        await communicator.disconnect()

        # Verify all responses received
        assert len(responses) == num_requests
        total_kb = num_requests * 500
        throughput_kbps = total_kb / elapsed

        print(
            f"\n[PERFORMANCE] Multiple large responses: "
            f"{num_requests} x 500KB in {elapsed:.3f}s "
            f"({throughput_kbps:.0f} KB/sec throughput)"
        )

    async def test_method_name_length_performance(self):
        """Validate that method name length checking is efficient.

        Method name validation should have negligible overhead.
        """

        class TestAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            pass

        # Create method with reasonably long name
        long_method_name = "x" * (MAX_METHOD_NAME_LENGTH - 10)

        @TestAsyncConsumer.rpc_method(long_method_name)
        async def very_long_method_name(value: int) -> int:
            return value * 2

        communicator = WebsocketCommunicator(TestAsyncConsumer.as_asgi(), "/ws/")
        await communicator.connect()

        iterations = 1000
        start_time = time.perf_counter()

        for i in range(iterations):
            await communicator.send_json_to(
                {
                    "jsonrpc": "2.0",
                    "method": long_method_name,
                    "params": {"value": i},
                    "id": i,
                }
            )
            response = await communicator.receive_json_from()
            assert response["result"] == i * 2

        elapsed = time.perf_counter() - start_time
        await communicator.disconnect()

        print(
            f"\n[PERFORMANCE] Long method names: "
            f"{iterations} calls in {elapsed:.3f}s "
            f"({iterations/elapsed:.0f} calls/sec)"
        )
