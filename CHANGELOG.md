# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Breaking Changes

#### Strict JSON-RPC 2.0 Compliance
- **Removed legacy `call_id` support**: All RPC messages must use the standard `id` field per JSON-RPC 2.0 specification. The non-standard `call_id` field is no longer recognized.
- **Removed mixed message format support**: Only pure JSON-RPC 2.0 format is now accepted. The legacy format with separate `request` and `response` wrapper fields has been removed.
- **Strict `jsonrpc` field validation**: All RPC requests must include `"jsonrpc": "2.0"` field. Requests without this field or with incorrect version will be rejected with `INVALID_REQUEST` error.
- **Removed batch call support code**: Commented-out batch call implementation has been removed. Batch calls are not supported.

#### Python Version
- **Minimum Python version raised to 3.10**: Updated from 3.9 to 3.10 to leverage modern Python features and type hints.

#### Dependencies
- **Removed `six` library**: Eliminated Python 2/3 compatibility layer as Python 2 is EOL.

### Added
- Added deprecation warning to `create_json_rpc_frame()` function. Users should migrate to:
  - `create_json_rpc_request()` for creating requests
  - `create_json_rpc_response()` for creating responses
  - `create_json_rpc_error_response()` for creating error responses

### Changed
- Simplified `intercept_call()` methods in both sync and async base classes, reducing complexity from ~70-140 lines to ~60 lines
- Updated pre-commit hooks to latest versions (black, ruff, isort, pre-commit-hooks)
- Improved error messages with better context
- Fixed type annotations (`is_notification: bool | None` instead of `is_notification: bool = None`)
- Updated code to use Python 3.10+ features (`isinstance(x, list | dict)` instead of `isinstance(x, (list, dict))`)

### Developer Experience
- Added `mypy` to dev dependencies for type checking
- Added `pytest-asyncio` for async test support
- Added `pytest-cov` for coverage reporting
- Updated all tool configurations to target Python 3.10

## Migration Guide

### From Legacy Format to JSON-RPC 2.0

**Old (no longer supported):**
```python
# Using call_id
{"call_id": "123", "method": "test", "arguments": {}}

# Mixed format
{"request": {"method": "test", "id": "123"}, "response": null}
```

**New (required):**
```python
# Standard JSON-RPC 2.0
{"jsonrpc": "2.0", "method": "test", "params": {}, "id": "123"}

# Notification (no response expected)
{"jsonrpc": "2.0", "method": "test", "params": {}}
```

### Update Your Client Code

1. **Replace `call_id` with `id`**: Search your codebase for any usage of `"call_id"` and replace with `"id"`.

2. **Add `jsonrpc` field**: Ensure all RPC requests include `"jsonrpc": "2.0"`.

3. **Use `params` instead of `arguments`**: While `arguments` is still supported for backward compatibility, prefer using standard `params` field.

4. **Remove mixed format wrappers**: If you're using `{"request": {...}, "response": {...}}` format, switch to pure JSON-RPC 2.0 format.

5. **Update function calls**: If using deprecated `create_json_rpc_frame()`, migrate to the new functions:
   ```python
   # Old
   frame = create_json_rpc_frame(rpc_id=123, method="test", params={})

   # New
   frame = create_json_rpc_request(rpc_id=123, method="test", params={})
   ```

## [0.3.6] - 2024-10-XX

Previous release before major refactoring.
