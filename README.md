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
- ✅ **Well tested** - 244 tests with 83% coverage

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
| -32000 | `GENERIC_APPLICATION_ERROR` | Application-level error |
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

It is intended to be used as a WebSocket consumer:

```python
from channels_rpc import JsonRpcWebsocketConsumer

class MyJsonRpcConsumer(JsonRpcWebsocketConsumer):

    def connect(self, message, **kwargs):
        """Perform things on WebSocket connection start"""
        self.accept()
        print("connect")
        # Do stuff if needed

    def disconnect(self, message, **kwargs):
        """Perform things on WebSocket connection close"""
        print("disconnect")
        # Do stuff if needed

```

JsonRpcWebsocketConsumer derives from `channels`
[JsonWebsocketConsumer](https://channels.readthedocs.io/en/latest/topics/consumers.html#websocketconsumer).
Then, the last step is to create the RPC methos hooks using the `rpc_method`
decorator:

```python
@MyJsonRpcConsumer.rpc_method()
def ping():
    return "pong"
```

Or, with a custom name:

```python
@MyJsonRpcConsumer.rpc_method("mymodule.rpc.ping")
def ping():
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
def ping(fake_an_error):
    if fake_an_error:
        # Will return an error to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}} #  <-- {"id": 1, "jsonrpc": "2.0", "error": {"message": "fake_error", "code": -32000, "data": ["fake_error"]}}  raise Exception("fake_error")
    else:
        # Will return a result to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}} #  <-- {"id": 1, "jsonrpc": "2.0", "result": "pong"}  return "pong"
```

## Async Use

Simply derive your customer from an asynchronous customer like
`AsyncJsonRpcWebsocketConsumer`:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class MyAsyncJsonRpcConsumer(AsyncJsonRpcWebsocketConsumer):
	pass

@MyAsyncJsonRpcConsumer.rpc_method("mymodule.rpc.ping")
async def ping(fake_an_error):
    return "ping"
```

## Database Access in Async Methods

For async RPC methods that need to access Django ORM, use the `@database_rpc_method()` decorator:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer
from myapp.models import User

class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    pass

@MyConsumer.database_rpc_method()
def get_user(user_id: int):
    """Get user information.

    Note: This is a SYNC function that will be automatically
    wrapped with database_sync_to_async.
    """
    user = User.objects.get(id=user_id)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
    }

@MyConsumer.database_rpc_method("users.list")
def list_users(limit: int = 10):
    """List users."""
    users = User.objects.all()[:limit]
    return [{"id": u.id, "username": u.username} for u in users]
```

**Important**: The decorated function should be synchronous (not async), as it will be automatically wrapped with `database_sync_to_async`.

## [Accessing Consumer and Request Context](#consumer)

RPC methods can access the consumer instance, request metadata, and Django Channels scope through the `RpcContext` parameter. When a method's first parameter (after `self` for bound methods) is typed as `RpcContext`, it will be automatically injected during execution.

```python
from channels_rpc import RpcContext

@MyJsonRpcConsumer.rpc_method()
def json_rpc_method(ctx: RpcContext, param1: str):
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
from channels_rpc import JsonRpcWebsocketConsumer, RpcContext

class MyJsonRpcConsumer(JsonRpcWebsocketConsumer):
    # Set to True to automatically port users from HTTP cookies
    # (you don't need channel_session_user, this implies it)
    # https://channels.readthedocs.io/en/stable/generics.html#websockets
    http_user = True

@MyJsonRpcConsumer.rpc_method()
def ping(ctx: RpcContext):
    # Access session through context
    ctx.scope["session"]["test"] = True

    # Log the request
    print(f"Ping called with ID {ctx.rpc_id}")

    return "pong"

@MyJsonRpcConsumer.rpc_method()
def get_user_info(ctx: RpcContext):
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

channels-rpc uses Python's logging module with the logger name `"django.channels.rpc"`. Configure it in your Django settings:

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
        'django.channels.rpc': {
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

## What's New in 1.0.0

### Performance Improvements

- **31x faster method execution** - Cached introspection eliminates reflection overhead on every call
- **Optimized logging** - Lazy evaluation prevents unnecessary string formatting
- **Reduced code duplication** - Shared validation logic between sync/async implementations

### Type Safety

- **Zero mypy errors** - Comprehensive type hints throughout
- **Protocol classes** - Proper typing for Django Channels mixin methods
- **IntEnum error codes** - Type-safe error code handling with IDE autocomplete

### Security Enhancements

- **DoS protection** - Automatic request size validation
- **Sanitized error responses** - Never leak internal details to clients
- **Specific exception handling** - No more generic exception catching

### Code Quality

- **244 tests** with 83% coverage
- **Pre-commit hooks** with mypy, ruff, black, isort
- **Clean public API** - Explicit `__all__` exports

## Breaking Changes in 1.0.0

### 1. Error Codes Now Use IntEnum

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

### 2. HTTP Transport Removed

The HTTP transport has been removed. This library now focuses exclusively on WebSocket transport.

**What was removed:**
- `AsyncRpcHttpConsumer` class
- `RPC_ERROR_TO_HTTP_CODE` mapping
- Individual error code constant exports

**Migration:**
- Use `AsyncJsonRpcWebsocketConsumer` instead of `AsyncRpcHttpConsumer`
- Import `JsonRpcErrorCode` enum instead of individual constants
- Update routing to use WebSocket endpoints

### 3. Empty List Parameters

Empty list parameters now correctly return `[]` instead of `{}` (bug fix).

### 4. JsonRpcError Constructor

The `rpc_id` parameter now accepts `str | int | None` (was `int`).

### Why These Changes

These changes align with the actual usage pattern in QSpace server (the downstream consumer), improve type safety, and eliminate maintenance overhead while making the library more robust and performant.
