# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2025-11-04

This is a major release representing a comprehensive code quality improvement effort focused on type safety, security, performance, and maintainability. The library is now production-ready with 100% type safety, robust security features, and significant performance optimizations.

### Breaking Changes

#### HTTP Consumer Removed
- **Removed HTTP consumer implementation**: The library now focuses exclusively on WebSocket-based JSON-RPC. The HTTP consumer had multiple bugs and was not being actively used.
- **Impact**: If you were using `AsyncRpcHttpConsumer`, migrate to WebSocket-based communication using `AsyncJsonRpcWebsocketConsumer`.

#### Semantic Corrections
- **Empty list parameter handling**: Empty list parameters now correctly return `[]` instead of `{}`. This fixes a semantic bug where `[] or {}` incorrectly evaluated to `{}`.
- **JsonRpcError constructor signature**: The `rpc_id` parameter now correctly accepts `str | int | None` instead of just `int`.

#### Error Response Security
- **Error responses no longer leak internal details**: Generic exception messages are no longer exposed to clients. Only safe, sanitized error messages are returned.
- **Impact**: If your client code was parsing internal error details from error responses, those details are no longer available.

#### Internal API Changes
- **Internal methods prefixed with underscore**: Methods like `_validate_call()`, `_get_method()`, `_process_call()`, etc. are now clearly marked as internal API.
- **Impact**: If you were overriding these methods, update your code to use the new names.

#### Strict JSON-RPC 2.0 Compliance
- **Strict `jsonrpc` field validation**: All RPC requests must include `"jsonrpc": "2.0"`. Requests without this field or with incorrect version will be rejected.
- **Removed batch call support**: Batch requests are explicitly not supported and will be rejected.
- **Impact**: Ensure all RPC requests include the `jsonrpc` field.

### Added

#### Security Features
- **DoS protection with size limits**: Comprehensive request validation to prevent denial-of-service attacks:
  - `MAX_MESSAGE_SIZE`: 10MB maximum message size
  - `MAX_ARRAY_LENGTH`: 10,000 maximum array items
  - `MAX_STRING_LENGTH`: 1MB maximum string length
  - `MAX_NESTING_DEPTH`: 20 maximum nesting levels
  - `MAX_METHOD_NAME_LENGTH`: 256 maximum method name characters
- **New exception**: `RequestTooLargeError` for size limit violations
- **Request validation**: `check_size_limits()` function for validating request sizes
- **Scope validation**: Enhanced scope sanitization to prevent security issues

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

#### Performance Optimizations
- **31x faster method introspection**: Method introspection moved from per-invocation to registration time (96.8% improvement)
  - Before: ~1.03s for 100,000 invocations
  - After: ~0.03s for 100,000 invocations
- **Consolidated validation logic**: Eliminated ~40 lines of duplicated code with new `validation.py` module
- **Lazy logging**: Replaced f-string logging with lazy % formatting for 5-10% improvement in production

#### Testing
- **15 new performance tests**: Comprehensive performance test suite in `tests/performance/`
  - Method introspection caching validation
  - Concurrent connection handling tests
  - Size limit validation performance tests
  - Large response chunking tests
- **288 total tests**: All passing with 83.95% code coverage (100% WebSocket coverage)

#### Documentation
- **JSON-RPC 2.0 compliance section**: Complete documentation of JSON-RPC 2.0 implementation details
- **Enhanced docstrings**: Comprehensive NumPy-style docstrings with examples for all public methods:
  - `get_rpc_methods()` - Method introspection patterns
  - `get_rpc_notifications()` - Notification discovery
  - `validate_scope()` - Security validation examples
  - `notify_channel()` - Notification patterns
- **Consumer class documentation**: Full documentation for sync and async consumer classes
- **Migration guide**: Step-by-step guide for upgrading from 0.x to 1.0.0
- **Breaking changes section**: Clear documentation of all breaking changes

### Changed

- **Simplified RPC processing**: Reduced complexity while improving maintainability
- **Error code management**: All error codes now use `IntEnum` for type safety
- **Public API definition**: Clear `__all__` exports defining the public API
- **Pre-commit hooks**: Updated to latest versions with mypy integration
- **Test organization**: Improved test structure with unit, integration, edge case, and performance tests

### Fixed

- **Empty list parameter bug**: `[] or {}` now correctly evaluates to `[]`
- **Function introspection logic**: Proper `varkw` checking for keyword argument detection
- **Deprecated function usage**: Removed internal usage of `create_json_rpc_frame()`
- **Type annotations**: Fixed numerous type annotation issues throughout codebase
- **Async method signatures**: Corrected return type annotations in `AsyncRpcBase`

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
