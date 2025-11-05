# channels-rpc

`channels-rpc` enables [JSON-RPC 2.0](https://www.jsonrpc.org/specification) functionality on top of Django Channels WebSockets with strict protocol compliance, type safety, and production-ready features.

## Features

- ✅ **Strict JSON-RPC 2.0 compliance** - Fully implements the JSON-RPC 2.0 specification
- ✅ **Django Channels integration** - Built on Django Channels for WebSocket support
- ✅ **Type safety** - Comprehensive type hints with mypy validation (0 type errors)
- ✅ **Security** - DoS protection with request size limits, no information leakage
- ✅ **Performance** - Optimized with cached introspection (31x faster method execution)
- ✅ **WebSocket only** - Focused on real-time bidirectional communication (HTTP removed in 1.0.0)
- ✅ **Easy integration** - Simple decorator-based API
- ✅ **Django settings** - Runtime configuration via Django settings (new in 1.0.0)
- ✅ **Lifecycle signals** - Monitor RPC calls with Django signals (new in 1.0.0)
- ✅ **Middleware support** - Extensible middleware pipeline for cross-cutting concerns (new in 1.0.0)
- ✅ **Custom serialization** - Support for custom JSON encoders (new in 1.0.0)
- ✅ **Permission control** - Decorator-based authorization with Django permissions (new in 1.0.0)
- ✅ **API introspection** - Discover methods, signatures, and documentation at runtime (new in 1.0.0)
- ✅ **Well tested** - 363 tests with 88% coverage

## JSON-RPC 2.0 Compliance

channels-rpc implements the [JSON-RPC 2.0 specification](https://www.jsonrpc.org/specification) with strict protocol adherence.

### Supported Features

**Version Checking**
- Only `"jsonrpc": "2.0"` is accepted
- Other versions are rejected with `INVALID_REQUEST` error (-32600)
- Validation enforced in `channels_rpc/rpc_base.py`

**Request Format**
- **Required fields**: `jsonrpc` (string), `method` (string)
- **Optional fields**: `params` (object or array), `id` (string, number, or null)
- **Notification requests**: Requests without `id` are treated as notifications (no response sent)

```javascript
// Method call (expects response)
{
    "jsonrpc": "2.0",
    "method": "subtract",
    "params": {"minuend": 42, "subtrahend": 23},
    "id": 1
}

// Notification (no response)
{
    "jsonrpc": "2.0",
    "method": "notify",
    "params": {"message": "hello"}
}
```

**Response Format**
- **Success response**: Contains `result` field
- **Error response**: Contains `error` object with `code` (integer), `message` (string), and optional `data` field
- All responses include `jsonrpc: "2.0"` and `id` matching the request

```javascript
// Success
{"jsonrpc": "2.0", "result": 19, "id": 1}

// Error
{
    "jsonrpc": "2.0",
    "error": {
        "code": -32601,
        "message": "Method Not Found: 'nonexistent'",
        "data": {"method": "nonexistent"}
    },
    "id": 1
}
```

**Parameter Formats**
- **Named parameters** (object): `"params": {"name": "value"}`
- **Positional parameters** (array): `"params": [1, 2, 3]`
- **Empty/omitted**: Both `"params": {}` and omitted params field are valid

**Error Codes**

Standard JSON-RPC 2.0 error codes (defined in `channels_rpc/exceptions.py`):

| Code | Constant | Meaning |
|------|----------|---------|
| -32700 | `PARSE_ERROR` | Invalid JSON received |
| -32600 | `INVALID_REQUEST` | JSON is not a valid Request object |
| -32601 | `METHOD_NOT_FOUND` | Method does not exist |
| -32602 | `INVALID_PARAMS` | Invalid method parameters |
| -32603 | `INTERNAL_ERROR` | Internal JSON-RPC error |

Server-defined error codes (-32099 to -32000):

| Code | Constant | Meaning |
|------|----------|---------|
| -32000 | `GENERIC_APPLICATION_ERROR` | Generic application error (deprecated, use specific codes) |
| -32001 | `REQUEST_TOO_LARGE` | Request exceeds size limits |
| -32701 | `PARSE_RESULT_ERROR` | Error serializing result |

**Request Size Limits**

To prevent denial-of-service attacks, the following limits are enforced (see `channels_rpc/limits.py`):

- **MAX_MESSAGE_SIZE**: 10MB per message
- **MAX_ARRAY_LENGTH**: 10,000 items in params array
- **MAX_STRING_LENGTH**: 1MB per string parameter
- **MAX_NESTING_DEPTH**: 20 levels of nested objects/arrays
- **MAX_METHOD_NAME_LENGTH**: 256 characters

Requests exceeding these limits return `REQUEST_TOO_LARGE` error (-32001).

### NOT Supported

**Batch Requests**

Batch requests (arrays of multiple JSON-RPC requests) are **intentionally not supported**. Each WebSocket message must contain a single JSON-RPC request or notification.

```javascript
// NOT SUPPORTED - will be rejected
[
    {"jsonrpc": "2.0", "method": "sum", "params": [1, 2], "id": 1},
    {"jsonrpc": "2.0", "method": "subtract", "params": [42, 23], "id": 2}
]
```

To execute multiple methods, send separate WebSocket messages for each request.

## Installation

```sh
$ pip install git+ssh://git@github.com/quantivly/channels-rpc.git
```

## Use

It is intended to be used as a WebSocket consumer. Use the async consumer `AsyncJsonRpcWebsocketConsumer`:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class MyJsonRpcConsumer(AsyncJsonRpcWebsocketConsumer):

    async def connect(self):
        """Perform things on WebSocket connection start"""
        await self.accept()
        print("connect")
        # Do stuff if needed

    async def disconnect(self, code):
        """Perform things on WebSocket connection close"""
        print("disconnect")
        # Do stuff if needed

```

AsyncJsonRpcWebsocketConsumer derives from `channels`
[AsyncJsonWebsocketConsumer](https://channels.readthedocs.io/en/latest/topics/consumers.html#asyncjsonwebsocketconsumer).
Then, the last step is to create the RPC method hooks using the `rpc_method`
decorator:

```python
@MyJsonRpcConsumer.rpc_method()
async def ping():
    return "pong"
```

Or, with a custom name:

```python
@MyJsonRpcConsumer.rpc_method("mymodule.rpc.ping")
async def ping():
    return "pong"
```

Will now be callable with `"method":"mymodule.rpc.ping"` in the rpc call:

```javascript
{
    "id":1,
    "jsonrpc":"2.0",
    "method":"mymodule.rpc.ping",
    "params":{}
}
```

RPC methods can obviously accept parameters. They also return "results" or "errors":

```python
@MyJsonRpcConsumer.rpc_method("mymodule.rpc.ping")
async def ping(fake_an_error):
    if fake_an_error:
        # Will return an error to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}} #  <-- {"id": 1, "jsonrpc": "2.0", "error": {"message": "fake_error", "code": -32000, "data": ["fake_error"]}}  raise Exception("fake_error")
    else:
        # Will return a result to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}} #  <-- {"id": 1, "jsonrpc": "2.0", "result": "pong"}  return "pong"
```

## [Accessing Consumer and Request Context](#consumer)

RPC methods can access the consumer instance, request metadata, and Django Channels scope through the `RpcContext` parameter. When a method's first parameter (after `self` for bound methods) is typed as `RpcContext`, it will be automatically injected during execution.

```python
from channels_rpc import RpcContext

@MyJsonRpcConsumer.rpc_method()
async def json_rpc_method(ctx: RpcContext, param1: str):
    # Access the consumer instance
    consumer = ctx.consumer

    # Access Django Channels scope (sessions, user, etc.)
    session = ctx.scope.get("session", {})

    # Access request metadata
    method_name = ctx.method_name  # "json_rpc_method"
    rpc_id = ctx.rpc_id  # Request ID from JSON-RPC call
    is_notification = ctx.is_notification  # False for methods, True for notifications

    # Do something with the context
    return f"Hello {param1}"
```

**Complete Example:**

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer, RpcContext

class MyJsonRpcConsumer(AsyncJsonRpcWebsocketConsumer):
    pass

@MyJsonRpcConsumer.rpc_method()
async def ping(ctx: RpcContext):
    # Access session through context
    ctx.scope["session"]["test"] = True

    # Log the request
    print(f"Ping called with ID {ctx.rpc_id}")

    return "pong"

@MyJsonRpcConsumer.rpc_method()
async def get_user_info(ctx: RpcContext):
    # Access authenticated user from scope
    user = ctx.scope.get("user")
    if user and user.is_authenticated:
        return {
            "username": user.username,
            "email": user.email
        }
    return {"error": "Not authenticated"}
```

**Available Context Attributes:**

- `ctx.consumer`: The consumer instance handling the RPC request
- `ctx.method_name`: Name of the RPC method being called
- `ctx.rpc_id`: Request ID from the JSON-RPC call (None for notifications)
- `ctx.is_notification`: Whether this is a notification (no response expected)
- `ctx.scope`: Django Channels scope dict containing:
  - `client`: (host, port) tuple
  - `headers`: Request headers
  - `cookies`: Request cookies
  - `session`: Django session (if http_user enabled)
  - `user`: Authenticated user (if http_user enabled)

## Testing

The JsonRpcConsumer class can be tested the same way Channels Consumers are tested.
See [here](http://channels.readthedocs.io/en/stable/testing.html)

## Logging Configuration

channels-rpc uses Python's logging module with the logger name `"channels_rpc"`. Configure it in your Django settings:

```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'channels_rpc': {
            'handlers': ['console'],
            'level': 'INFO',  # Use 'DEBUG' for detailed RPC call logging
            'propagate': False,
        },
    },
}
```

**Log Levels:**
- `DEBUG` - Detailed RPC method execution, parameter logging
- `INFO` - Connection events, application errors
- `WARNING` - Invalid requests, unexpected data
- `ERROR` - Internal errors (should not occur in production)

## Security Features

### Request Size Limits (DoS Protection)

channels-rpc enforces size limits to prevent denial-of-service attacks:

- **MAX_MESSAGE_SIZE**: 10MB per message
- **MAX_ARRAY_LENGTH**: 10,000 items in params array
- **MAX_STRING_LENGTH**: 1MB per string parameter
- **MAX_NESTING_DEPTH**: 20 levels of nested objects
- **MAX_METHOD_NAME_LENGTH**: 256 characters

These limits are enforced automatically. Oversized requests return a `JsonRpcErrorCode.REQUEST_TOO_LARGE` error.

### Error Response Sanitization

Error responses never leak internal details:
- Generic exceptions return sanitized messages
- Stack traces are logged but not sent to clients
- Parameter validation errors include only safe context

### Scope Validation

Call `self.validate_scope()` in your `connect()` method to validate WebSocket connection metadata:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class MyJsonRpcConsumer(AsyncJsonRpcWebsocketConsumer):
    async def connect(self):
        self.validate_scope()  # Validates scope structure
        await self.accept()
```

## Error Handling

channels-rpc uses an IntEnum for error codes:

```python
from channels_rpc import JsonRpcErrorCode, JsonRpcError

# Standard JSON-RPC 2.0 error codes
JsonRpcErrorCode.PARSE_ERROR          # -32700
JsonRpcErrorCode.INVALID_REQUEST      # -32600
JsonRpcErrorCode.METHOD_NOT_FOUND     # -32601
JsonRpcErrorCode.INVALID_PARAMS       # -32602
JsonRpcErrorCode.INTERNAL_ERROR       # -32603

# Server-defined error codes
JsonRpcErrorCode.GENERIC_APPLICATION_ERROR  # -32000
JsonRpcErrorCode.REQUEST_TOO_LARGE          # -32001
JsonRpcErrorCode.PARSE_RESULT_ERROR         # -32701
```

Raise `JsonRpcError` in your RPC methods for controlled error responses:

```python
from channels_rpc import JsonRpcError, JsonRpcErrorCode

@MyConsumer.rpc_method()
def my_method(value):
    if value < 0:
        raise JsonRpcError(
            rpc_id=None,  # Will be filled automatically
            code=JsonRpcErrorCode.INVALID_PARAMS,
            data={"field": "value", "constraint": "must be non-negative"}
        )
    return value * 2
```

### Error Code Usage Guide

Choose the appropriate error code to help clients handle errors correctly:

**Standard Protocol Errors - Automatically generated:**

- `PARSE_ERROR` - Automatically raised by framework for invalid JSON
- `INVALID_REQUEST` - Automatically raised for malformed JSON-RPC requests
- `METHOD_NOT_FOUND` - Automatically raised when method doesn't exist
- `INVALID_PARAMS` - Use for parameter validation failures
- `INTERNAL_ERROR` - Internal server errors

**Application Errors:**

- `GENERIC_APPLICATION_ERROR` - Generic application-level errors (deprecated, prefer specific custom codes)
- `REQUEST_TOO_LARGE` - Automatically raised when size limits exceeded
- `PARSE_RESULT_ERROR` - Result serialization failures

**Best Practices:**

1. **Use standard codes when appropriate** - The JSON-RPC 2.0 spec codes cover most common scenarios
2. **Include data field** - Provide context about what went wrong
3. **Don't leak secrets** - Never include passwords, tokens, or internal paths in error data
4. **Be consistent** - Use the same error codes for similar failures across your API

**Example:**

```python
from channels_rpc import JsonRpcError, JsonRpcErrorCode, RpcContext

@MyConsumer.rpc_method()
async def update_user(ctx: RpcContext, user_id: int, email: str):
    # Input validation failure
    if not validate_email(email):
        raise JsonRpcError(
            ctx.rpc_id,
            JsonRpcErrorCode.INVALID_PARAMS,
            data={"field": "email", "error": "Invalid format"}
        )

    # Application-level error
    try:
        user = await User.objects.aget(id=user_id)
    except User.DoesNotExist:
        raise JsonRpcError(
            ctx.rpc_id,
            JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
            data={"resource": "user", "id": user_id}
        )

    user.email = email
    await user.asave()
    return {"success": True}
```

## Configuration

Configure channels-rpc via Django settings under the `CHANNELS_RPC` key:

```python
# settings.py
CHANNELS_RPC = {
    # Size limits for DoS protection (all optional, defaults shown)
    'MAX_MESSAGE_SIZE': 10 * 1024 * 1024,  # 10MB
    'MAX_ARRAY_LENGTH': 10000,
    'MAX_STRING_LENGTH': 1024 * 1024,  # 1MB
    'MAX_NESTING_DEPTH': 20,
    'MAX_METHOD_NAME_LENGTH': 256,

    # Logging configuration
    'LOG_RPC_PARAMS': False,  # Set True only in development (may expose PII)
    'SANITIZE_ERRORS': True,  # Always sanitize errors in responses
}
```

Access configuration programmatically:

```python
from channels_rpc.config import get_config

config = get_config()
print(config.limits.max_message_size)  # 10485760
```

## Middleware

Middleware provides a way to add cross-cutting concerns to RPC request/response handling:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class LoggingMiddleware:
    def process_request(self, data, consumer):
        print(f"RPC call: {data.get('method')}")
        return data

    def process_response(self, response, consumer):
        print(f"RPC response: {response.get('id')}")
        return response

class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    # Middleware applied in order
    middleware = [
        LoggingMiddleware(),
        # Add more middleware...
    ]
```

**Built-in Middleware** (in `channels_rpc.middleware`):
- `LoggingMiddleware` - Example middleware that logs RPC calls with timing

**Middleware Patterns** (see `examples/comprehensive_example.py`):
- Custom middleware implementation
- Request/response processing
- Authentication and logging patterns

## Signals

Monitor RPC lifecycle with Django signals:

```python
from channels_rpc.signals import rpc_method_started, rpc_method_completed, rpc_method_failed
import logging

logger = logging.getLogger(__name__)

def log_rpc_call(sender, method_name, duration, **kwargs):
    logger.info(f"RPC {method_name} completed in {duration:.3f}s")

def alert_on_error(sender, method_name, error, **kwargs):
    logger.error(f"RPC {method_name} failed: {error}")

rpc_method_completed.connect(log_rpc_call)
rpc_method_failed.connect(alert_on_error)
```

**Available signals:**
- `rpc_method_started` - Method execution starts
- `rpc_method_completed` - Method completes successfully
- `rpc_method_failed` - Method raises error
- `rpc_client_connected` - WebSocket client connects
- `rpc_client_disconnected` - WebSocket client disconnects

## Permission-Based Access Control

Restrict RPC methods with Django permissions:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer, RpcContext
from channels_rpc.decorators import permission_required

class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    pass

@MyConsumer.rpc_method()
@permission_required('myapp.can_delete_users')
async def delete_user(ctx: RpcContext, user_id: int):
    # Only users with permission can call this
    User.objects.get(id=user_id).delete()
    return {'deleted': True}

@MyConsumer.rpc_method()
@permission_required('myapp.view_reports', 'myapp.export_data')
async def export_report(ctx: RpcContext, report_id: int):
    # User must have BOTH permissions
    return generate_report(report_id)
```

**Security Note:** Unauthorized calls return `METHOD_NOT_FOUND` (not auth error) to prevent method enumeration.

## Custom JSON Encoder

Serialize custom types (datetime, Decimal, dataclasses):

```python
import json
from datetime import datetime
from decimal import Decimal
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)

class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    json_encoder_class = CustomEncoder

@MyConsumer.rpc_method()
async def get_data():
    return {
        'timestamp': datetime.now(),  # Serialized as ISO string
        'amount': Decimal('123.45'),  # Serialized as float
    }
```

## API Introspection

Discover available methods and generate documentation:

```python
# List all methods
methods = MyConsumer.get_rpc_methods()
# ['add', 'subtract', 'get_user']

# Get detailed method info
info = MyConsumer.get_method_info('get_user')
# MethodInfo(
#     name='get_user',
#     signature='(ctx: RpcContext, user_id: int) -> dict',
#     docstring='Get user by ID...',
#     accepts_context=True,
#     transport_options={'websocket': True}
# )

# Generate complete API description (OpenRPC-compatible)
api_doc = MyConsumer.describe_api()
# {
#     'methods': [...],
#     'notifications': [...],
#     'consumer_class': 'MyConsumer'
# }
```

## What's New in 1.0.0

### New Features

**🎯 Django Settings Integration**
- Configure size limits, logging, and behavior via `CHANNELS_RPC` Django setting
- Runtime configuration without code changes
- See [Configuration](#configuration) section

**📡 Lifecycle Signals**
- Monitor RPC calls with 5 Django signals: `rpc_method_started`, `rpc_method_completed`, `rpc_method_failed`, `rpc_client_connected`, `rpc_client_disconnected`
- Integrate with APM tools (DataDog, New Relic, etc.)
- Track performance metrics and errors
- See [Signals](#signals) section

**🔌 Middleware Support**
- Extensible middleware pipeline for cross-cutting concerns
- Protocol-based middleware system via `RpcMiddleware` protocol
- Example middleware: `LoggingMiddleware` for call tracking
- Middleware patterns in `examples/comprehensive_example.py`
- See [Middleware](#middleware) section

**Note**: Rate limiting, connection limits, and request tracking are **application-level concerns** in channels-rpc. The library provides the middleware framework and examples, but implementations are application-specific. For production deployments, see QSpace server's implementation as a reference.

**🔧 Custom JSON Encoder**
- Support for custom JSON encoders (datetime, Decimal, dataclasses, etc.)
- Set `json_encoder_class` attribute on consumer
- Automatic fallback to str() for non-serializable objects

**🔐 Permission-Based Access Control**
- `@permission_required()` decorator for Django permission integration
- Automatic authorization checking before method execution
- Security-first design (returns METHOD_NOT_FOUND to prevent enumeration)

**🔍 API Introspection**
- `get_method_info(method_name)` - Get detailed method metadata
- `describe_api()` - Generate OpenRPC-compatible API descriptions
- Runtime method discovery for documentation generation

**📊 Comprehensive Error Handling**
- Standard JSON-RPC 2.0 error codes (PARSE_ERROR, INVALID_REQUEST, METHOD_NOT_FOUND, INVALID_PARAMS, INTERNAL_ERROR)
- Server-defined error codes (GENERIC_APPLICATION_ERROR, REQUEST_TOO_LARGE, PARSE_RESULT_ERROR)
- Type-safe `JsonRpcErrorCode` IntEnum

### Performance Improvements

- **31x faster method execution** - Cached introspection eliminates reflection overhead on every call
- **Optimized logging** - Lazy evaluation prevents unnecessary string formatting
- **Reduced code duplication** - Eliminated 150+ lines of duplicate decorator code
- **Pre-parse size validation** - Prevents DoS attacks by checking size before JSON parsing

### Type Safety

- **Zero mypy errors** - Comprehensive type hints throughout
- **Protocol classes** - Proper typing for Django Channels mixin methods
- **IntEnum error codes** - Type-safe error code handling with IDE autocomplete
- **RpcContext dataclass** - Type-safe context parameter

### Security Enhancements

- **DoS protection** - Pre-parse message size validation
- **Sanitized error responses** - Never leak internal details to clients
- **Specific exception handling** - RuntimeError no longer masked (indicates bugs)
- **Protocol compliance** - Fixed critical JSON-RPC 2.0 violations (null ID handling)

### Code Quality

- **363 tests** with 88% coverage (+119 new tests)
- **Pre-commit hooks** with mypy, ruff, black, isort
- **Clean public API** - Explicit `__all__` exports
- **Eliminated duplication** - Shared decorator logic in `decorators.py`

## Breaking Changes in 1.0.0

### 1. HTTP Parameter Removed from Decorators

The `http` parameter has been completely removed from all decorators.

**Old:**
```python
@MyConsumer.rpc_method(websocket=True, http=False)
def my_method():
    ...
```

**New:**
```python
@MyConsumer.rpc_method(websocket=True)
def my_method():
    ...
```

**Migration:** Remove the `http` parameter from all decorator calls.

### 2. Logger Name Changed

The logger name changed from `"django.channels.rpc"` to `"channels_rpc"` to follow Django conventions.

**Old Django settings:**
```python
LOGGING = {
    'loggers': {
        'django.channels.rpc': {  # Old name
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

**New Django settings:**
```python
LOGGING = {
    'loggers': {
        'channels_rpc': {  # New name
            'handlers': ['console'],
            'level': 'DEBUG',
        },
    },
}
```

### 3. Null ID Now Requires Response

Fixed JSON-RPC 2.0 compliance: `"id": null` now correctly requires a response (not treated as notification).

**Behavior change:**
- Notification: Request **WITHOUT** `id` field (no response)
- Request with null ID: Request **WITH** `"id": null` (must receive response)

This is a **protocol fix** - the previous behavior was non-compliant.

### 4. Error Codes Now Use IntEnum

**Old:**
```python
from channels_rpc import INVALID_REQUEST, METHOD_NOT_FOUND
error = JsonRpcError(rpc_id, INVALID_REQUEST)
```

**New:**
```python
from channels_rpc import JsonRpcErrorCode
error = JsonRpcError(rpc_id, JsonRpcErrorCode.INVALID_REQUEST)
```

### 5. Consumer Context via RpcContext (Recommended)

While `**kwargs` still works, the recommended approach is using `RpcContext`:

**Old (still works but deprecated):**
```python
@MyConsumer.rpc_method()
async def get_user(**kwargs):
    consumer = kwargs.get('consumer')
    user = consumer.scope.get('user')
```

**New (recommended):**
```python
from channels_rpc import RpcContext

@MyConsumer.rpc_method()
async def get_user(ctx: RpcContext):
    user = ctx.scope.get('user')
```

### 6. HTTP Transport Removed

The HTTP transport has been removed. This library now focuses exclusively on WebSocket transport.

**What was removed:**
- `AsyncRpcHttpConsumer` class
- `RPC_ERROR_TO_HTTP_CODE` mapping
- Individual error code constant exports

**Migration:**
- Use `AsyncJsonRpcWebsocketConsumer` instead of `AsyncRpcHttpConsumer`
- Import `JsonRpcErrorCode` enum instead of individual constants
- Update routing to use WebSocket endpoints

### 7. Exception Handling Changed

`RuntimeError` is no longer caught as an application error (it indicates bugs).

**Impact:** `RuntimeError` exceptions will now be logged as internal errors instead of application errors.
**Migration:** If your code intentionally raises `RuntimeError` for application logic, use `ValueError` or `TypeError` instead.

## Production Deployment

### Configuration Checklist

For production deployments, ensure these settings are properly configured:

```python
# settings.py (PRODUCTION)
CHANNELS_RPC = {
    # Size limits - adjust based on your use case
    'MAX_MESSAGE_SIZE': 10 * 1024 * 1024,  # 10MB default

    # Security - always enabled in production
    'SANITIZE_ERRORS': True,  # Never leak stack traces
    'LOG_RPC_PARAMS': False,  # Never log params (may contain PII)
}
```

### Failure Modes and Graceful Degradation

**Scenario: Database Unavailable**
- Methods accessing Django ORM will fail
- Use `database_sync_to_async` from `channels.db` for safe database access in async methods
- **Mitigation**: Implement database connection pooling and read replicas

**Scenario: Redis (Channel Layer) Unavailable**
- WebSocket connections will fail to establish
- Existing connections may experience message delivery delays
- **Mitigation**: Use Redis Sentinel or Cluster for high availability

**Scenario: Middleware Errors**
- Request middleware errors: Returns `INTERNAL_ERROR`, request rejected
- Response middleware errors: Original response sent, error logged
- **Mitigation**: Test middleware thoroughly, handle exceptions internally

**Scenario: Method Execution Timeout**
- Async methods: Timeout enforced via `@rpc_method(timeout=60)`
- Sync methods: No timeout enforcement (limitation)
- **Mitigation**: Use async consumers for timeout guarantees

**Scenario: Message Size Limit Exceeded**
- Request rejected with `REQUEST_TOO_LARGE` error
- Connection remains open, client can retry with smaller payload
- **Mitigation**: Implement chunking/pagination at application level

**Scenario: Rate Limit Exceeded** (Application-Level)
- Implementation-specific (see QSpace server for reference)
- Generally: Request rejected with custom application error
- **Mitigation**: Implement exponential backoff in clients

### Security Best Practices

1. **Always set `SANITIZE_ERRORS: True` in production** - Prevents information disclosure
2. **Never set `LOG_RPC_PARAMS: True` in production** - May log PII/credentials
3. **Validate all inputs** - Use `INVALID_PARAMS` for invalid data
4. **Implement connection limits** - Prevent resource exhaustion (see QSpace example)
5. **Use HTTPS/WSS** - Never expose WebSocket endpoints over unencrypted connections
6. **Implement authentication** - Use middleware or `@permission_required` decorator
7. **Monitor error rates** - Use signals to track `rpc_method_failed` events

### Performance Recommendations

1. **Use async consumers** - Better concurrency and timeout support
2. **Cache method introspection** - Already done automatically (31x speedup)
3. **Implement connection pooling** - For database connections in async methods
4. **Monitor promise cleanup** - Track periodic cleanup in logs
5. **Set appropriate size limits** - Balance security vs functionality

### Why These Changes

These changes improve protocol compliance, type safety, maintainability, and align with Django best practices. The library is now production-ready for high-scale deployments while eliminating technical debt.
