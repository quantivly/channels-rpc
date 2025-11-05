"""Tests for utility functions in channels_rpc.utils.

Coverage: JSON-RPC message builders and deprecated frame function.
Target: 25-30 tests, 95%+ coverage of utils.py
"""

from __future__ import annotations

import warnings

import pytest

from channels_rpc.utils import (
    create_json_rpc_error_response,
    create_json_rpc_frame,
    create_json_rpc_request,
    create_json_rpc_response,
)


@pytest.mark.unit
class TestCreateJsonRpcRequest:
    """Test create_json_rpc_request() function."""

    def test_create_request_with_all_params(self):
        """Should create request with rpc_id, method, and params."""
        result = create_json_rpc_request(
            rpc_id=1, method="test_method", params={"key": "value"}
        )

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["method"] == "test_method"
        assert result["params"] == {"key": "value"}

    def test_create_request_with_dict_params(self):
        """Should create request with dict parameters."""
        params = {"arg1": "value1", "arg2": 123}
        result = create_json_rpc_request(rpc_id=2, method="test", params=params)

        assert result["params"] == params

    def test_create_request_with_list_params(self):
        """Should create request with list parameters."""
        params = [1, 2, 3, "test"]
        result = create_json_rpc_request(rpc_id=3, method="test", params=params)

        assert result["params"] == params

    def test_create_request_without_params(self):
        """Should create request without params field when None."""
        result = create_json_rpc_request(rpc_id=4, method="test")

        assert "params" not in result
        assert result["method"] == "test"

    def test_create_notification_without_id(self):
        """Should create notification (no id field) when rpc_id is None."""
        result = create_json_rpc_request(method="notify", params={"event": "test"})

        assert "id" not in result
        assert result["method"] == "notify"

    def test_create_request_with_string_rpc_id(self):
        """Should accept string rpc_id."""
        result = create_json_rpc_request(rpc_id="abc123", method="test")

        assert result["id"] == "abc123"

    def test_create_request_with_none_method(self):
        """Should accept None method (though not spec-compliant)."""
        result = create_json_rpc_request(rpc_id=1, method=None)

        assert result["method"] is None

    def test_request_always_has_jsonrpc_2_0(self):
        """Should always include jsonrpc: '2.0' field."""
        result = create_json_rpc_request(rpc_id=1, method="test")

        assert result["jsonrpc"] == "2.0"


@pytest.mark.unit
class TestCreateJsonRpcResponse:
    """Test create_json_rpc_response() function."""

    def test_create_success_response(self):
        """Should create success response with result."""
        result = create_json_rpc_response(rpc_id=1, result={"data": "test"})

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["result"] == {"data": "test"}
        assert "error" not in result

    def test_create_error_response(self):
        """Should create error response with error object."""
        error = {"code": -32600, "message": "Invalid Request"}
        result = create_json_rpc_response(rpc_id=2, error=error)

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 2
        assert result["error"] == error
        assert "result" not in result

    def test_create_response_with_none_result(self):
        """Should include result field even when None."""
        result = create_json_rpc_response(rpc_id=3, result=None)

        assert result["result"] is None
        assert "result" in result

    def test_create_response_with_compressed_flag(self):
        """Should include compressed field when True."""
        result = create_json_rpc_response(rpc_id=4, result="data", compressed=True)

        assert result["compressed"] is True

    def test_create_response_without_compressed_flag(self):
        """Should not include compressed field when False."""
        result = create_json_rpc_response(rpc_id=5, result="data", compressed=False)

        assert "compressed" not in result

    def test_create_response_with_string_rpc_id(self):
        """Should accept string rpc_id."""
        result = create_json_rpc_response(rpc_id="xyz", result="success")

        assert result["id"] == "xyz"

    def test_create_response_with_none_rpc_id(self):
        """Should accept None rpc_id."""
        result = create_json_rpc_response(rpc_id=None, result="data")

        assert result["id"] is None

    def test_error_response_no_compressed_flag(self):
        """Should not include compressed field for error responses."""
        error = {"code": -32000, "message": "Error"}
        result = create_json_rpc_response(
            rpc_id=6, error=error, compressed=True  # compressed ignored for errors
        )

        assert "compressed" not in result
        assert "error" in result

    def test_response_always_has_jsonrpc_2_0(self):
        """Should always include jsonrpc: '2.0' field."""
        result = create_json_rpc_response(rpc_id=7, result="test")

        assert result["jsonrpc"] == "2.0"


@pytest.mark.unit
class TestCreateJsonRpcErrorResponse:
    """Test create_json_rpc_error_response() function."""

    def test_create_error_response_with_all_params(self):
        """Should create error response with all parameters."""
        result = create_json_rpc_error_response(
            rpc_id=1, code=-32600, message="Invalid Request", data={"field": "method"}
        )

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["error"]["code"] == -32600
        assert result["error"]["message"] == "Invalid Request"
        assert result["error"]["data"] == {"field": "method"}

    def test_create_error_response_without_data(self):
        """Should create error response without data field when None."""
        result = create_json_rpc_error_response(
            rpc_id=2, code=-32601, message="Method not found"
        )

        assert result["error"]["code"] == -32601
        assert result["error"]["message"] == "Method not found"
        assert "data" not in result["error"]

    def test_create_error_response_default_values(self):
        """Should use default error code and message."""
        result = create_json_rpc_error_response(rpc_id=3)

        assert result["error"]["code"] == -32603
        assert result["error"]["message"] == "Internal error"

    def test_create_error_response_with_string_rpc_id(self):
        """Should accept string rpc_id."""
        result = create_json_rpc_error_response(
            rpc_id="test", code=-32600, message="Error"
        )

        assert result["id"] == "test"

    def test_create_error_response_with_none_rpc_id(self):
        """Should accept None rpc_id."""
        result = create_json_rpc_error_response(
            rpc_id=None, code=-32700, message="Parse error"
        )

        assert result["id"] is None

    @pytest.mark.parametrize(
        "code,message",
        [
            (-32700, "Parse Error"),
            (-32600, "Invalid Request"),
            (-32601, "Method Not Found"),
            (-32602, "Invalid Params"),
            (-32603, "Internal Error"),
            (-32000, "Application Error"),
        ],
    )
    def test_create_error_response_all_error_codes(self, code, message):
        """Should create error response for all standard error codes."""
        result = create_json_rpc_error_response(rpc_id=1, code=code, message=message)

        assert result["error"]["code"] == code
        assert result["error"]["message"] == message

    def test_error_response_structure(self):
        """Should have correct JSON-RPC 2.0 error response structure."""
        result = create_json_rpc_error_response(rpc_id=4, code=-32000, message="Test")

        assert "jsonrpc" in result
        assert "id" in result
        assert "error" in result
        assert "code" in result["error"]
        assert "message" in result["error"]
        assert "result" not in result


@pytest.mark.unit
class TestCreateJsonRpcFrameDeprecated:
    """Test deprecated create_json_rpc_frame() function."""

    def test_deprecated_warning(self):
        """Should emit DeprecationWarning when called."""
        with pytest.warns(
            DeprecationWarning, match="create_json_rpc_frame.*deprecated"
        ):
            create_json_rpc_frame(rpc_id=1, result="test")

    def test_create_request_via_frame(self):
        """Should create request when result is None."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = create_json_rpc_frame(
                rpc_id=1, method="test_method", params={"key": "value"}
            )

        assert result["jsonrpc"] == "2.0"
        assert result["method"] == "test_method"
        assert result["params"] == {"key": "value"}

    def test_create_success_response_via_frame(self):
        """Should create success response when result provided."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = create_json_rpc_frame(rpc_id=2, result={"data": "test"})

        assert result["jsonrpc"] == "2.0"
        assert result["result"] == {"data": "test"}

    def test_create_error_response_via_frame(self):
        """Should create error response when error provided."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            error: dict[str, int | str] = {"code": -32600, "message": "Invalid"}
            result = create_json_rpc_frame(rpc_id=3, result="ignored", error=error)

        assert result["jsonrpc"] == "2.0"
        assert "error" in result
        assert result["error"]["code"] == -32600

    def test_frame_with_compressed_flag(self):
        """Should pass compressed flag to response."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            result = create_json_rpc_frame(rpc_id=4, result="data", compressed=True)

        assert result.get("compressed") is True

    def test_frame_ignores_rpc_id_key_parameter(self):
        """Should ignore rpc_id_key parameter (legacy)."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            # rpc_id_key was used in old format, should be ignored now
            result = create_json_rpc_frame(
                rpc_id=5, result="test", rpc_id_key="call_id"
            )

        # Should use 'id' not 'call_id'
        assert "id" in result
        assert result["id"] == 5
        assert "call_id" not in result

    def test_frame_error_with_missing_fields(self):
        """Should handle error dict with missing fields gracefully."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            # Error dict missing message
            error: dict[str, int | str] = {"code": -32000}
            result = create_json_rpc_frame(rpc_id=6, result="test", error=error)

        assert result["error"]["code"] == -32000
        assert result["error"]["message"] == "Internal error"  # default

    def test_frame_error_without_code(self):
        """Should use default error code when not provided."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            error: dict[str, int | str] = {"message": "Custom error"}
            result = create_json_rpc_frame(rpc_id=7, result="test", error=error)

        assert result["error"]["code"] == -32603  # default INTERNAL_ERROR
