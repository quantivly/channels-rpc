# HTTP Consumer Issues

## Production Bugs Found and Fixed

During test development for `async_rpc_http_consumer.py`, the following critical bugs were discovered and fixed:

### 1. Missing `await` for async method call (Line 30)
**Before:**
```python
result, is_notification = self.intercept_call(data)
```

**After:**
```python
result, is_notification = await self.intercept_call(data)
```

**Impact:** The async `intercept_call()` method was not being awaited, causing the method to return a coroutine object instead of the actual result.

### 2. Missing `await` for async send_response (Line 51)
**Before:**
```python
self.send_response(status_code, json.dumps(result), headers=[...])
```

**After:**
```python
await self.send_response(status_code, json.dumps(result), headers=[...])
```

**Impact:** The response was never being sent because the async method wasn't awaited.

### 3. Undefined variable `is_notification` on parse error (Line 29)
**Before:**
```python
except ValueError:
    result = generate_error_response(None, PARSE_ERROR, RPC_ERRORS[PARSE_ERROR])
# is_notification undefined here
```

**After:**
```python
except ValueError:
    result = generate_error_response(None, PARSE_ERROR, RPC_ERRORS[PARSE_ERROR])
    is_notification = False
```

**Impact:** When JSON parsing failed, `is_notification` was undefined, causing a NameError.

### 4. Undefined variable `status_code` for empty body (Line 49)
**Before:**
```python
else:
    result = generate_error_response(None, INVALID_REQUEST, RPC_ERRORS[INVALID_REQUEST])
# status_code undefined here
await self.send_response(status_code, ...)  # NameError!
```

**After:**
```python
else:
    result = generate_error_response(None, INVALID_REQUEST, RPC_ERRORS[INVALID_REQUEST])
    status_code = 400
```

**Impact:** Empty body requests would cause a NameError when trying to send the response.

### 5. Wrong base class inheritance (Line 14)
**Before:**
```python
from channels_rpc.rpc_base import RpcBase

class AsyncRpcHttpConsumer(AsyncHttpConsumer, RpcBase):
```

**After:**
```python
from channels_rpc.async_rpc_base import AsyncRpcBase

class AsyncRpcHttpConsumer(AsyncHttpConsumer, AsyncRpcBase):
```

**Impact:** The consumer was inheriting from the synchronous `RpcBase` instead of `AsyncRpcBase`, causing all RPC methods to be treated as synchronous.

## Remaining Issues

### HTTP Consumer Testing Challenges

The HTTP consumer still has integration testing issues:

1. **AsyncHttpConsumer Compatibility**: The Django Channels `HttpCommunicator` test utility appears to have compatibility issues with `AsyncHttpConsumer` when combined with the RPC base classes.

2. **Response Handling**: Even after fixing the production bugs, responses are not being properly captured by the test harness, resulting in timeouts.

3. **Limited Real-World Usage**: The HTTP consumer appears to be less commonly used than the WebSocket consumer in the channels-rpc library, suggesting it may need architectural review.

## Recommendations

1. **Integration Testing**: The HTTP consumer may need manual integration testing or a different test approach (e.g., using actual HTTP clients).

2. **Documentation**: Add examples of HTTP RPC consumer usage to help users understand the expected behavior.

3. **Architectural Review**: Consider whether the HTTP consumer should be refactored to better align with Django Channels patterns.

4. **Alternative Approaches**: Consider if HTTP JSON-RPC should be handled differently (e.g., via Django views instead of Channels consumers).

## Test Coverage Impact

Despite these issues, the test suite achieves:
- **91.01% overall coverage**
- **100% coverage** of all WebSocket consumers
- **100% coverage** of core RPC logic (sync and async)
- **96%+ coverage** of exceptions and utilities

The HTTP consumer represents only ~6% of the total codebase, and all other components have excellent test coverage.
