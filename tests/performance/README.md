# Performance Tests

This directory contains performance and load tests for the channels-rpc library to validate performance-critical paths and detect regressions.

## Test Categories

### 1. Method Introspection Cache Performance
Tests validating the 31x speedup from caching method introspection at registration time rather than on every invocation.

**Key tests:**
- `test_method_introspection_cache_basic` - Verifies `accepts_context` is cached
- `test_cached_introspection_performance_benchmark` - Benchmarks 100k calls (target: <2s)
- `test_async_cached_introspection_performance` - Async method cache validation

**Baseline:** 66,000+ calls/sec for sync methods, 8,000+ calls/sec for async methods

### 2. Concurrent Connection Handling
Tests validating concurrent RPC request handling without race conditions or performance degradation.

**Key tests:**
- `test_concurrent_method_calls_same_connection` - 100 concurrent requests on one connection
- `test_multiple_concurrent_connections` - 20 concurrent connections
- `test_concurrent_notifications` - 100 concurrent notifications

**Baseline:** 800+ req/sec per connection, 7,500+ req/sec across multiple connections

### 3. Size Limit Validation Performance
Tests validating that security checks (DoS prevention) have minimal overhead.

**Key tests:**
- `test_small_payload_validation_overhead` - Small payloads (<1KB): <0.01ms
- `test_medium_payload_validation_overhead` - Medium payloads (~100KB): <1ms
- `test_large_payload_near_limit_validation` - Large payloads (~1MB): <0.01ms
- `test_deeply_nested_payload_validation` - Nested structures: <0.1ms
- `test_array_with_many_items_validation` - Large arrays: <10ms

**Baseline:** Sub-millisecond validation for most payloads

### 4. Large Response Chunking Performance
Tests validating performance with large responses that may require chunking and compression.

**Key tests:**
- `test_large_response_method_call` - 2MB response handling
- `test_multiple_concurrent_large_responses` - 10x 500KB concurrent responses
- `test_method_name_length_performance` - Long method names (~256 chars)

**Baseline:** 200+ MB/sec throughput for large responses

## Running Tests

### Run all performance tests:
```bash
poetry run pytest -m performance -v
```

### Run only fast performance tests (exclude slow):
```bash
poetry run pytest -m "performance and not slow" -v
```

### Run with performance output visible:
```bash
poetry run pytest -m performance -v -s
```

### Run specific test class:
```bash
poetry run pytest tests/performance/test_load.py::TestMethodIntrospectionCachePerformance -v
```

### Run in CI/CD (without slow tests):
```bash
poetry run pytest -m "performance and not slow" --tb=short
```

## Performance Markers

Tests use pytest markers for organization:

- `@pytest.mark.performance` - All performance/load tests
- `@pytest.mark.slow` - Tests that take >1 second (10 tests)
- `@pytest.mark.asyncio` - Async tests requiring event loop

## Performance Thresholds

Current performance targets (as of 2025-11):

| Metric | Target | Test |
|--------|--------|------|
| Method introspection cache | 60,000+ calls/sec | test_cached_introspection_performance_benchmark |
| Async method calls | 8,000+ calls/sec | test_async_cached_introspection_performance |
| Concurrent requests | 800+ req/sec | test_concurrent_method_calls_same_connection |
| Small payload validation | <0.01ms | test_small_payload_validation_overhead |
| Medium payload validation | <1ms | test_medium_payload_validation_overhead |
| Large response throughput | 200+ MB/sec | test_large_response_method_call |

## Adding New Performance Tests

When adding new performance tests:

1. Use `@pytest.mark.performance` for all performance tests
2. Add `@pytest.mark.slow` if test takes >1 second
3. Include performance output with `print(f"[PERFORMANCE] ...")`
4. Document baseline metrics in test docstrings
5. Use `time.perf_counter()` for accurate timing
6. Temporarily reduce logging for high-iteration benchmarks

Example:
```python
@pytest.mark.performance
@pytest.mark.slow
def test_my_performance_metric(self):
    """Test my feature performance.

    Target: X operations in <Y seconds.
    """
    import logging

    # Reduce logging noise
    logger = logging.getLogger("channels_rpc")
    original_level = logger.level
    logger.setLevel(logging.WARNING)

    try:
        start = time.perf_counter()
        # ... run benchmark ...
        elapsed = time.perf_counter() - start

        assert elapsed < threshold
        print(f"[PERFORMANCE] Feature: {ops} ops in {elapsed:.3f}s")
    finally:
        logger.setLevel(original_level)
```

## Interpreting Results

Performance test failures can indicate:

1. **Regression:** Code changes slowed down critical paths
2. **Environment:** System under load, different hardware
3. **Test flakiness:** Network delays, I/O contention

If tests fail:
- Run multiple times to confirm consistency
- Check system resources (CPU, memory, I/O)
- Review recent code changes for performance impact
- Compare against baseline metrics in this README

## Continuous Integration

In CI/CD pipelines:

```yaml
# Run fast performance tests (no slow marker)
- poetry run pytest -m "performance and not slow"

# Run full performance suite on nightly builds
- poetry run pytest -m performance
```
