"""Canonical JSON-RPC message examples for testing."""

from __future__ import annotations

# ============================================================================
# Valid Messages
# ============================================================================

VALID_REQUEST = {
    "jsonrpc": "2.0",
    "method": "test_method",
    "params": {"arg": "value"},
    "id": 1,
}

VALID_REQUEST_WITH_LIST_PARAMS = {
    "jsonrpc": "2.0",
    "method": "test_method",
    "params": [1, 2, 3],
    "id": 2,
}

VALID_REQUEST_NO_PARAMS = {
    "jsonrpc": "2.0",
    "method": "test_method",
    "id": 3,
}

VALID_NOTIFICATION = {
    "jsonrpc": "2.0",
    "method": "test_notification",
    "params": {"event": "test"},
    # No id = notification
}

VALID_RESPONSE_SUCCESS = {
    "jsonrpc": "2.0",
    "result": "success",
    "id": 1,
}

VALID_RESPONSE_ERROR = {
    "jsonrpc": "2.0",
    "error": {
        "code": -32600,
        "message": "Invalid Request",
    },
    "id": 1,
}


# ============================================================================
# Invalid Messages
# ============================================================================

INVALID_MISSING_VERSION = {
    "method": "test",
    "id": 1,
    # Missing jsonrpc field
}

INVALID_WRONG_VERSION = {
    "jsonrpc": "1.0",
    "method": "test",
    "id": 1,
}

INVALID_VERSION_AS_NUMBER = {
    "jsonrpc": 2.0,  # Should be string "2.0"
    "method": "test",
    "id": 1,
}

INVALID_MISSING_METHOD = {
    "jsonrpc": "2.0",
    "id": 1,
    # Missing method field
}

INVALID_METHOD_AS_NUMBER = {
    "jsonrpc": "2.0",
    "method": 123,  # Should be string
    "id": 1,
}

INVALID_PARAMS_AS_STRING = {
    "jsonrpc": "2.0",
    "method": "test",
    "params": "not a dict or list",
    "id": 1,
}


# ============================================================================
# Edge Cases
# ============================================================================

EDGE_EMPTY_PARAMS = {
    "jsonrpc": "2.0",
    "method": "test",
    "params": {},
    "id": 1,
}

EDGE_LEGACY_ARGUMENTS_FIELD = {
    "jsonrpc": "2.0",
    "method": "test",
    "arguments": {"legacy": True},  # Old format
    "id": 1,
}
