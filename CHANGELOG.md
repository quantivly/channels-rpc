# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Server-side request ID collision detection**: Added tracking of recent request IDs with 10-second cooldown period to prevent replay attacks and request ID reuse issues. Uses lazy initialization for compatibility with Django Channels consumer lifecycle.

### Fixed
- **Exception handling in RPC processing**: Removed overly broad `Exception` from exception handler in `_intercept_call()`. Now only catches specific application-level exceptions (`JsonRpcError`, `ValueError`, `TypeError`, `KeyError`, `AttributeError`), allowing system exceptions and unexpected errors to propagate correctly for proper debugging and error handling.

## [1.0.0] - 2025-11-04

This is a major release representing a comprehensive refactoring and enhancement effort. The library is now production-ready with new features for monitoring, configuration, security, and extensibility while fixing critical protocol violations and eliminating technical debt.

### Breaking Changes

#### 1. HTTP Parameter Removed from Decorators

**Removed the `http` parameter** from `@rpc_method()`, `@rpc_notification()`, and `@database_rpc_method()` decorators.

**Migration:**
```python
# Before
@MyConsumer.rpc_method(websocket=True, http=False)

# After
@MyConsumer.rpc_method(websocket=True)
```

#### 2. Logger Name Changed

**Changed logger name** from `"django.channels.rpc"` to `"channels_rpc"` to follow Django conventions.

**Migration:** Update Django logging configuration:
```python
# Before
LOGGING = {'loggers': {'django.channels.rpc': {...}}}

# After
LOGGING = {'loggers': {'channels_rpc': {...}}}
```

#### 3. JSON-RPC 2.0 Protocol Compliance Fixes

**Fixed null ID handling** - `"id": null` now correctly requires a response (was incorrectly treated as notification).
- **Notification**: Request WITHOUT `id` field
- **Request with null ID**: Request WITH `"id": null` (must receive response)

**Added ID type validation** - Request IDs must be string, number, or null (rejects objects, arrays, etc.)

**Impact:** Clients sending `"id": null` will now receive responses. This fixes a critical protocol violation.

#### 4. Exception Handling Changed

**`RuntimeError` no longer caught** as application error - it now propagates to the generic Exception handler, indicating a bug.

**Impact:** If your code raises `RuntimeError` for application logic, use `ValueError` or `TypeError` instead.

#### 5. HTTP Consumer Removed

**Removed HTTP consumer implementation** - library now focuses exclusively on WebSocket-based JSON-RPC.

**Migration:** Use `AsyncJsonRpcWebsocketConsumer` instead of `AsyncRpcHttpConsumer`.

#### 6. Empty List Parameters

**Fixed bug** - Empty list parameters now correctly return `[]` instead of `{}`.

#### 7. RpcContext Recommended Over **kwargs

While `**kwargs` still works, **RpcContext is now the recommended approach** for accessing consumer context.

**Migration:**
```python
# Before (still works)
@MyConsumer.database_rpc_method()
def my_method(**kwargs):
    consumer = kwargs.get('consumer')

# After (recommended)
from channels_rpc import RpcContext

@MyConsumer.database_rpc_method()
def my_method(ctx: RpcContext):
    consumer = ctx.consumer
```

### Added

#### Django Integration Features
- **Django settings integration** (`config.py`, `apps.py`):
  - Configure size limits via `CHANNELS_RPC` Django setting
  - Runtime configuration without code changes
  - `RpcConfig` and `RpcLimits` classes for programmatic access
  - `ChannelsRpcConfig` AppConfig for Django app initialization
- **Django signals for lifecycle monitoring** (`signals.py`):
  - `rpc_method_started` - Emitted when method execution begins
  - `rpc_method_completed` - Emitted on successful completion
  - `rpc_method_failed` - Emitted when method raises error
  - `rpc_client_connected` - Emitted on WebSocket connection
  - `rpc_client_disconnected` - Emitted on disconnection
  - Includes duration tracking and error details for APM integration

#### Middleware System
- **Extensible middleware pipeline** (`middleware.py`):
  - `RpcMiddleware` protocol for custom middleware
  - Process requests before execution and responses before transmission
  - Support for both sync and async middleware
- **Six built-in middleware classes**:
  - `RateLimitMiddleware` - Per-method token bucket rate limiting
  - `AuthenticationMiddleware` - Require authentication for all methods
  - `LoggingMiddleware` - Structured logging of all RPC calls
  - `CachingMiddleware` - Time-based response caching
  - `CompressionMiddleware` - zstd compression for large responses
  - `RequestIDMiddleware` - Unique ID tracking for request correlation

#### Database Features
- **Atomic transaction support** in `@database_rpc_method`:
  - `atomic=True` (default) - Wrap in Django atomic transaction
  - `using='db_alias'` - Specify which database to use
  - Ensures data integrity for multi-step operations
- **Enhanced error handling** for Django ORM exceptions

#### Enhanced Error Codes
- **Seven new server-defined error codes** for better error categorization:
  - `-32002` `VALIDATION_ERROR` - Invalid input data (client error)
  - `-32003` `RESOURCE_NOT_FOUND` - Resource doesn't exist (client error)
  - `-32004` `PERMISSION_DENIED` - Authorization failure (client error)
  - `-32005` `CONFLICT` - State conflict (client error)
  - `-32006` `RATE_LIMIT_EXCEEDED` - Too many requests (client error)
  - `-32010` `DATABASE_ERROR` - Transient database failure (server error)
  - `-32011` `EXTERNAL_SERVICE_ERROR` - External dependency failed (server error)
- **Error categorization utilities**:
  - `JsonRpcErrorCode.is_client_error()` - Check if error is client-side
  - `JsonRpcErrorCode.is_server_error()` - Check if error is server-side
- **Deprecated** `GENERIC_APPLICATION_ERROR` (still works, use specific codes instead)

#### Security Features
- **Pre-parse size validation** - Check message size BEFORE JSON parsing (prevents DoS)
- **ID field type validation** - Validates ID is string, number, or null per spec
- **DoS protection with size limits**: Comprehensive request validation:
  - `MAX_MESSAGE_SIZE`: 10MB maximum message size
  - `MAX_ARRAY_LENGTH`: 10,000 maximum array items
  - `MAX_STRING_LENGTH`: 1MB maximum string length
  - `MAX_NESTING_DEPTH`: 20 maximum nesting levels
  - `MAX_METHOD_NAME_LENGTH`: 256 maximum method name characters
- **New exception**: `RequestTooLargeError` for size limit violations
- **Enhanced error sanitization** - No internal details leaked in error responses

#### Permission-Based Access Control
- **`@permission_required()` decorator** (`decorators.py`):
  - Integrates with Django's permission system
  - Supports single or multiple permissions
  - Returns `METHOD_NOT_FOUND` to prevent method enumeration (security-first)
  - Works with both sync and async methods

#### Custom JSON Serialization
- **Custom JSON encoder support**:
  - Set `json_encoder_class` attribute on consumer
  - Supports datetime, Decimal, dataclasses, and custom types
  - Automatic fallback to `str()` for non-serializable objects
  - Improved error handling for serialization failures

#### API Introspection
- **Method metadata API**:
  - `get_method_info(method_name)` - Returns `MethodInfo` with signature, docstring, context flag
  - `describe_api()` - Generates OpenRPC-compatible API description
  - Runtime method discovery for documentation generation
- **MethodInfo dataclass** - Comprehensive method metadata with signature introspection

#### Type Safety
- **Protocol classes**: New `protocols.py` module with Protocol classes for Django Channels mixin methods
- **RpcMethodWrapper dataclass**: Type-safe wrapper for method metadata with cached introspection results
- **Comprehensive type hints**: 100% type coverage with 0 mypy errors

#### Architecture Improvements
- **MethodRegistry class**: Replaces fragile `id(cls)` pattern with proper WeakKeyDictionary-based registry
  - Prevents memory leaks
  - Provides registry introspection methods
  - Singleton pattern via `get_registry()`
- **RpcContext dataclass**: Explicit context object for type-safe method parameters
  - Opt-in feature with full backward compatibility
  - Provides access to consumer, request_id, method_name, scope, etc.
  - Example usage documented in docstrings

#### Database Integration
- **@database_rpc_method decorator**: Helper for safely accessing Django ORM from async RPC methods
  - Automatically wraps sync database code with `database_sync_to_async`
  - Supports RpcContext injection
  - Comprehensive documentation and examples

#### Architecture & Code Quality
- **Eliminated code duplication** (`decorators.py`):
  - Created shared `inspect_accepts_context()` utility function
  - Removed 150+ lines of duplicate decorator code
  - Single source of truth for RpcContext parameter detection
- **Moved `RpcMethodWrapper` to `protocols.py`** - Better module organization, avoids circular imports
- **Shared decorator factory** - `create_rpc_method_wrapper()` for consistent wrapper creation

#### Performance Optimizations
- **31x faster method introspection**: Method introspection moved from per-invocation to registration time (96.8% improvement)
  - Before: ~1.03s for 100,000 invocations
  - After: ~0.03s for 100,000 invocations
- **Pre-parse size validation**: Prevents DoS by checking size before JSON parsing
- **Eliminated decorator duplication**: Reduced code paths, improved performance
- **Lazy logging**: Replaced f-string logging with lazy % formatting

#### Testing
- **+119 new tests**: Expanded test suite to 363 tests (up from 244)
  - 33 introspection API tests
  - 29 decorator tests (permission, context detection)
  - 25 integration tests
  - 15 performance tests
  - New middleware tests
- **88% code coverage** (up from 83%)
- **All 363 tests passing**

#### Documentation
- **Comprehensive README updates**:
  - Configuration section with Django settings examples
  - Middleware usage guide with built-in middleware
  - Signals integration examples for APM tools
  - Permission decorator documentation
  - Custom JSON encoder examples
  - API introspection guide
- **New example files**:
  - `examples/comprehensive_example.py` - Showcases all 1.0.0 features
  - `examples/database_usage.py` - Updated to use RpcContext
  - `examples/middleware_usage.py` - Middleware patterns
  - `examples/introspection_demo.py` - API discovery examples
- **Enhanced docstrings**: NumPy-style docstrings with examples throughout
- **Migration guide**: Clear instructions for all breaking changes

### Changed

- **Decorator implementation refactored**: All decorators now use shared logic from `decorators.py`
- **Error handling improved**: Better exception categorization, no more masking of bugs
- **Validation order optimized**: ID validation before version check for better error messages
- **Module organization**: Better separation of concerns (protocols, decorators, middleware, signals, config)
- **Test organization**: Better test structure with dedicated files for new features
- **Test organization**: Improved test structure with unit, integration, edge case, and performance tests

### Fixed

#### JSON-RPC 2.0 Protocol Compliance
- **Null ID handling** (CRITICAL): `"id": null` now correctly requires response instead of being treated as notification
  - Fixed violation of JSON-RPC 2.0 specification
  - Notifications are now correctly identified by **absence** of `id` field, not `null` value
- **ID field type validation**: Request IDs are now validated to be string, number, or null (rejects objects, arrays)
- **Parse error return value**: `decode_json()` now returns empty dict on parse error instead of None
- **Pre-parse DoS protection**: Message size validated BEFORE JSON parsing to prevent memory exhaustion attacks

#### Code Quality Fixes
- **Eliminated code duplication**: Removed 150+ lines of duplicate decorator logic
- **Exception handling**: `RuntimeError` no longer masked as application error (now correctly treated as bug indicator)
- **Circular import risks**: Moved `RpcMethodWrapper` to `protocols.py`, eliminated lazy imports
- **Empty list parameter bug**: `[] or {}` now correctly evaluates to `[]`
- **Function introspection logic**: Proper parameter inspection with better error handling
- **Type annotations**: Fixed type annotation issues throughout codebase

### Security

- **Information leakage eliminated**: Generic exception catching no longer leaks sensitive data
- **DoS protection**: Comprehensive size limits prevent resource exhaustion attacks
- **Scope sanitization**: Enhanced validation prevents scope-related security issues
- **Error message safety**: All error responses are sanitized before sending to clients

### Performance

- **Method execution**: 31x faster (96.8% improvement) due to cached introspection
- **Concurrent handling**: Successfully handles 100+ concurrent requests
- **Size validation**: <1ms overhead for most payloads
- **Large responses**: 200+ MB/sec throughput with chunking and compression

### Developer Experience

- **Zero mypy errors**: Complete type safety with comprehensive type hints
- **Better error messages**: Enhanced error messages with context
- **Registry introspection**: New methods for inspecting registered RPC methods
- **Example code**: Comprehensive examples for database integration patterns
- **Pre-commit integration**: Mypy included in pre-commit hooks for continuous type checking

## Migration Guide for 1.0.0

### HTTP Consumer Removal

If you were using the HTTP consumer:

**Before:**
```python
from channels_rpc import AsyncRpcHttpConsumer

class MyConsumer(AsyncRpcHttpConsumer):
    pass
```

**After:**
```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    pass
```

### Internal Method Usage

If you were overriding internal methods:

**Before:**
```python
def validate_call(self, data):
    # Custom validation
    pass
```

**After:**
```python
def _validate_call(self, data):
    # Custom validation
    pass
```

### Error Response Handling

If your client code was parsing error details:

**Before:**
```python
# Error responses included internal exception details
{"error": {"message": "ValueError: invalid input at /path/to/file.py:123"}}
```

**After:**
```python
# Error responses contain only safe, sanitized messages
{"error": {"message": "Invalid parameters", "code": -32602}}
```

### Using RpcContext (Optional)

New opt-in feature for type-safe context access:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer, RpcContext

class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    @MyConsumer.rpc_method()
    def my_method(context: RpcContext, param1: str):
        # Access consumer, request_id, method_name, scope
        consumer = context.consumer
        request_id = context.rpc_id
        scope = context.scope
        return {"result": "success"}
```

### Using Database Methods (Optional)

New helper for Django ORM access:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    @MyConsumer.database_rpc_method()
    def get_user(user_id: int):
        # This is a SYNC function that safely accesses Django ORM
        from myapp.models import User
        user = User.objects.get(id=user_id)
        return {"username": user.username, "email": user.email}
```

## [0.3.6] - 2024-10-XX

Previous release before major refactoring.
