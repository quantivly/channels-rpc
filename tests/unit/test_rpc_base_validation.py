"""Tests for RPC validation logic in rpc_base.py.

Coverage: validate_call(), get_params(), get_rpc_id(), and get_method().
Target: 45-50 tests, 100% coverage of validation logic.

These tests are CRITICAL as they cover:
- Recent JSON-RPC 2.0 strict compliance refactoring (commit 0ac8072)
- Variable scoping bug fixes (commits f5418a0, 317f958)
- Security-critical input validation
"""

from __future__ import annotations

from typing import Any

import pytest

from channels_rpc.exceptions import JsonRpcError, JsonRpcErrorCode


@pytest.mark.unit
class TestValidateCall:
    """Test validate_call() method - JSON-RPC 2.0 request validation."""

    def test_validate_call_with_valid_request(self, mock_rpc_consumer):
        """Should accept valid JSON-RPC 2.0 request."""
        valid_data = {
            "jsonrpc": "2.0",
            "method": "test_method",
            "params": {"key": "value"},
            "id": 1,
        }

        # Should not raise
        mock_rpc_consumer._validate_call(valid_data)

    def test_validate_call_without_params(self, mock_rpc_consumer):
        """Should accept request without params field."""
        data = {"jsonrpc": "2.0", "method": "test_method", "id": 1}

        # Should not raise
        mock_rpc_consumer._validate_call(data)

    def test_validate_call_without_id(self, mock_rpc_consumer):
        """Should accept notification (no id field)."""
        data = {"jsonrpc": "2.0", "method": "test_method", "params": {}}

        # Should not raise
        mock_rpc_consumer._validate_call(data)

    def test_validate_call_rejects_wrong_version_string(self, mock_rpc_consumer):
        """Should reject jsonrpc version other than '2.0' string."""
        data = {"jsonrpc": "1.0", "method": "test", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST
        assert "version" in exc_info.value.data
        assert exc_info.value.data["version"] == "1.0"

    @pytest.mark.parametrize(
        "version", ["2", "3.0", "2.0.0", "v2.0", "", "1.0", "null"]
    )
    def test_validate_call_rejects_various_wrong_versions(
        self, mock_rpc_consumer, version
    ):
        """Should reject all non-'2.0' string versions."""
        data = {"jsonrpc": version, "method": "test", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST
        assert exc_info.value.data["version"] == version

    def test_validate_call_rejects_numeric_version(self, mock_rpc_consumer):
        """Should reject numeric version 2.0 (must be string '2.0')."""
        data = {"jsonrpc": 2.0, "method": "test", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST
        assert exc_info.value.data["version"] == 2.0

    def test_validate_call_rejects_integer_version(self, mock_rpc_consumer):
        """Should reject integer version 2 (must be string '2.0')."""
        data = {"jsonrpc": 2, "method": "test", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST

    def test_validate_call_rejects_none_version(self, mock_rpc_consumer):
        """Should reject None jsonrpc version."""
        data = {"jsonrpc": None, "method": "test", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST

    def test_validate_call_rejects_missing_method(self, mock_rpc_consumer):
        """Should reject request without 'method' field."""
        data = {"jsonrpc": "2.0", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST
        assert "field" in exc_info.value.data
        assert "method" in exc_info.value.data["field"].lower()

    @pytest.mark.parametrize("method_value", [123, 45.6, True, False, None])
    def test_validate_call_rejects_non_string_method(
        self, mock_rpc_consumer, method_value
    ):
        """Should reject method that is not a string."""
        data = {"jsonrpc": "2.0", "method": method_value, "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST
        assert "field" in exc_info.value.data
        assert "string" in exc_info.value.data["field"].lower()

    def test_validate_call_rejects_method_as_list(self, mock_rpc_consumer):
        """Should reject method as list."""
        data = {"jsonrpc": "2.0", "method": ["test"], "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST
        assert "list" in exc_info.value.data["field"]

    def test_validate_call_rejects_method_as_dict(self, mock_rpc_consumer):
        """Should reject method as dict."""
        data = {"jsonrpc": "2.0", "method": {"name": "test"}, "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST
        assert "dict" in exc_info.value.data["field"]

    def test_validate_call_includes_rpc_id_in_error(self, mock_rpc_consumer):
        """Should include rpc_id in error when validation fails."""
        data = {"jsonrpc": "1.0", "method": "test", "id": 42}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._validate_call(data)

        assert exc_info.value.rpc_id == 42


@pytest.mark.unit
class TestGetParams:
    """Test get_params() method - parameter extraction and validation."""

    def test_get_params_with_dict(self, mock_rpc_consumer):
        """Should return dict parameters."""
        data = {"params": {"key": "value", "number": 123}}
        result = mock_rpc_consumer._get_params(data)

        assert result == {"key": "value", "number": 123}
        assert isinstance(result, dict)

    def test_get_params_with_list(self, mock_rpc_consumer):
        """Should return list parameters."""
        data = {"params": [1, 2, 3, "test"]}
        result = mock_rpc_consumer._get_params(data)

        assert result == [1, 2, 3, "test"]
        assert isinstance(result, list)

    def test_get_params_with_empty_dict(self, mock_rpc_consumer):
        """Should accept empty dict params."""
        data: dict[str, Any] = {"params": {}}
        result = mock_rpc_consumer._get_params(data)

        assert result == {}

    def test_get_params_with_empty_list(self, mock_rpc_consumer):
        """Should preserve empty list (bug fix for falsy value handling)."""
        data: dict[str, Any] = {"params": []}
        result = mock_rpc_consumer._get_params(data)

        # Bug fix: empty list should be preserved, not converted to {}
        assert result == []
        assert isinstance(result, list)

    def test_get_params_defaults_to_empty_dict(self, mock_rpc_consumer):
        """Should return empty dict when params not provided."""
        data = {"method": "test"}
        result = mock_rpc_consumer._get_params(data)

        assert result == {}
        assert isinstance(result, dict)

    def test_get_params_backward_compat_arguments(self, mock_rpc_consumer):
        """Should fall back to 'arguments' field for backward compatibility."""
        data = {"arguments": {"legacy": "value"}}
        result = mock_rpc_consumer._get_params(data)

        assert result == {"legacy": "value"}

    def test_get_params_prefers_params_over_arguments(self, mock_rpc_consumer):
        """Should prefer 'params' over 'arguments' when both present."""
        data = {"params": {"new": "value"}, "arguments": {"old": "value"}}
        result = mock_rpc_consumer._get_params(data)

        assert result == {"new": "value"}

    @pytest.mark.parametrize("invalid_params", ["string", 123, 45.6, True])
    def test_get_params_rejects_invalid_types(self, mock_rpc_consumer, invalid_params):
        """Should reject params that are not dict or list."""
        data = {"params": invalid_params, "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._get_params(data)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_PARAMS
        assert "expected" in exc_info.value.data
        assert "dict or list" in exc_info.value.data["expected"]

    def test_get_params_with_none_defaults_to_dict(self, mock_rpc_consumer):
        """Should treat None params as missing (defaults to {})."""
        data = {"params": None, "id": 1}
        result = mock_rpc_consumer._get_params(data)

        # None is falsy, so implementation defaults to {}
        assert result == {}

    def test_get_params_error_includes_actual_type(self, mock_rpc_consumer):
        """Should include actual type in error message."""
        data = {"params": "string_value", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._get_params(data)

        assert exc_info.value.data["actual"] == "str"

    def test_get_params_error_includes_rpc_id(self, mock_rpc_consumer):
        """Should include rpc_id in error."""
        data = {"params": 123, "id": 99}

        with pytest.raises(JsonRpcError) as exc_info:
            mock_rpc_consumer._get_params(data)

        assert exc_info.value.rpc_id == 99


@pytest.mark.unit
class TestGetRpcId:
    """Test get_rpc_id() method - RPC ID extraction."""

    def test_get_rpc_id_with_integer(self, mock_rpc_consumer):
        """Should extract integer rpc_id."""
        data = {"id": 42}
        rpc_id, key = mock_rpc_consumer._get_rpc_id(data)

        assert rpc_id == 42
        assert key == "id"

    def test_get_rpc_id_with_string(self, mock_rpc_consumer):
        """Should extract string rpc_id."""
        data = {"id": "test-123"}
        rpc_id, key = mock_rpc_consumer._get_rpc_id(data)

        assert rpc_id == "test-123"
        assert key == "id"

    def test_get_rpc_id_with_none(self, mock_rpc_consumer):
        """Should return None for notifications (no id field)."""
        data = {"method": "test"}
        rpc_id, key = mock_rpc_consumer._get_rpc_id(data)

        assert rpc_id is None
        assert key == "id"

    def test_get_rpc_id_always_returns_id_key(self, mock_rpc_consumer):
        """Should always return 'id' as the key (JSON-RPC 2.0 spec)."""
        data = {"id": 1}
        _, key = mock_rpc_consumer._get_rpc_id(data)

        assert key == "id"

    def test_get_rpc_id_with_zero(self, mock_rpc_consumer):
        """Should treat 0 as valid rpc_id."""
        data = {"id": 0}
        rpc_id, _ = mock_rpc_consumer._get_rpc_id(data)

        assert rpc_id == 0

    def test_get_rpc_id_with_negative_number(self, mock_rpc_consumer):
        """Should accept negative numbers as rpc_id."""
        data = {"id": -1}
        rpc_id, _ = mock_rpc_consumer._get_rpc_id(data)

        assert rpc_id == -1


@pytest.mark.unit
class TestGetMethod:
    """Test get_method() method - method lookup and protocol validation."""

    def test_get_method_for_registered_method(self, consumer_with_methods):
        """Should return registered method."""
        data = {"jsonrpc": "2.0", "method": "add", "id": 1}

        method = consumer_with_methods._get_method(data, is_notification=False)

        assert method.__name__ == "add"
        assert callable(method)

    def test_get_method_for_notification(self, consumer_with_methods):
        """Should lookup in rpc_notifications for notifications."""
        data = {"jsonrpc": "2.0", "method": "notify_event"}

        method = consumer_with_methods._get_method(data, is_notification=True)

        assert method.__name__ == "notify_event"

    def test_get_method_not_found(self, consumer_with_methods):
        """Should raise JsonRpcErrorCode.METHOD_NOT_FOUND for unknown method."""
        data = {"jsonrpc": "2.0", "method": "unknown_method", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            consumer_with_methods._get_method(data, is_notification=False)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert exc_info.value.data["method"] == "unknown_method"

    def test_get_method_validates_call_first(self, consumer_with_methods):
        """Should call _validate_call() before lookup."""
        data = {"jsonrpc": "1.0", "method": "add", "id": 1}

        # Should fail validation before lookup
        with pytest.raises(JsonRpcError) as exc_info:
            consumer_with_methods._get_method(data, is_notification=False)

        assert exc_info.value.code == JsonRpcErrorCode.INVALID_REQUEST

    def test_get_method_respects_websocket_flag(self, consumer_with_methods):
        """Should check websocket flag in method options."""
        # websocket_only method should work with websocket scope
        consumer_with_methods.scope = {"type": "websocket"}
        data = {"jsonrpc": "2.0", "method": "websocket_only", "id": 1}

        method = consumer_with_methods._get_method(data, is_notification=False)
        assert method.__name__ == "websocket_only"

    def test_get_method_rejects_http_only_on_websocket(self, consumer_with_methods):
        """Should reject http-only method on websocket."""
        consumer_with_methods.scope = {"type": "websocket"}
        data = {"jsonrpc": "2.0", "method": "http_only", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            consumer_with_methods._get_method(data, is_notification=False)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_get_method_respects_http_flag(self, consumer_with_methods):
        """Should check http flag in method options."""
        # http_only method should work with http scope
        consumer_with_methods.scope = {"type": "http"}
        data = {"jsonrpc": "2.0", "method": "http_only", "id": 1}

        method = consumer_with_methods._get_method(data, is_notification=False)
        assert method.__name__ == "http_only"

    def test_get_method_rejects_websocket_only_on_http(self, consumer_with_methods):
        """Should reject websocket-only method on http."""
        consumer_with_methods.scope = {"type": "http"}
        data = {"jsonrpc": "2.0", "method": "websocket_only", "id": 1}

        with pytest.raises(JsonRpcError) as exc_info:
            consumer_with_methods._get_method(data, is_notification=False)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_get_method_includes_rpc_id_in_error(self, consumer_with_methods):
        """Should include rpc_id in JsonRpcErrorCode.METHOD_NOT_FOUND error."""
        data = {"jsonrpc": "2.0", "method": "unknown", "id": 42}

        with pytest.raises(JsonRpcError) as exc_info:
            consumer_with_methods._get_method(data, is_notification=False)

        assert exc_info.value.rpc_id == 42
