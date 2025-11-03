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

## Installation

```sh
$ pip install git+ssh://git@github.com/quantivly/channels-rpc.git
```

## Use

It is intended to be used as a WebSocket consumer:

```python
from channels_rpc import JsonRpcWebsocketConsumer

class MyJsonRpcConsumer(JsonRpcConsumer):

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

## [Sessions and other parameters from Consumer object](#consumer)

The original channel message - that can contain sessions (if activated with
[http_user](https://channels.readthedocs.io/en/stable/generics.html#websockets))
and other important info can be easily accessed by retrieving the `**kwargs`
and get a parameter named _consumer_.

```python
MyJsonRpcConsumerTest.rpc_method()
def json_rpc_method(param1, **kwargs):
    consumer = kwargs["consumer"]
    ##do something with consumer
```

Example:

```python
class MyJsonRpcConsumerTest(JsonRpcConsumer):
    # Set to True to automatically port users from HTTP cookies
    # (you don't need channel_session_user, this implies it) # https://channels.readthedocs.io/en/stable/generics.html#websockets  http_user = True

....

@MyJsonRpcConsumerTest.rpc_method()
def ping(**kwargs):
    consumer = kwargs["consumer"]
    consumer.scope["session"]["test"] = True
    return "pong"

```

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
