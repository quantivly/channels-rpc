"""Tests for exception handling in channels_rpc.exceptions.

Coverage: JsonRpcError class, generate_error_response(), error message enhancement.
Target: 35-40 tests, 100% coverage of exceptions.py
"""

from __future__ import annotations

import json

import pytest

from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INTERNAL_ERROR,
    INVALID_PARAMS,
    INVALID_REQUEST,
    METHOD_NOT_FOUND,
    PARSE_ERROR,
    PARSE_RESULT_ERROR,
    RPC_ERRORS,
    JsonRpcError,
    generate_error_response,
)


@pytest.mark.unit
class TestJsonRpcErrorCreation:
    """Test JsonRpcError instantiation and attributes."""

    def test_create_with_required_params(self):
        """Should create JsonRpcError with rpc_id and code."""
        error = JsonRpcError(rpc_id=1, code=INVALID_REQUEST)

        assert error.rpc_id == 1
        assert error.code == INVALID_REQUEST
        assert error.data is None

    def test_create_with_data(self):
        """Should create JsonRpcError with additional data."""
        data = {"field": "method", "expected": "string"}
        error = JsonRpcError(rpc_id=2, code=INVALID_PARAMS, data=data)

        assert error.rpc_id == 2
        assert error.code == INVALID_PARAMS
        assert error.data == data

    @pytest.mark.parametrize(
        "rpc_id,code",
        [
            (1, PARSE_ERROR),
            (2, INVALID_REQUEST),
            (3, METHOD_NOT_FOUND),
            (4, INVALID_PARAMS),
            (5, INTERNAL_ERROR),
            (6, GENERIC_APPLICATION_ERROR),
        ],
    )
    def test_create_with_all_error_codes(self, rpc_id, code):
        """Should create error for all defined error codes."""
        error = JsonRpcError(rpc_id=rpc_id, code=code)

        assert error.rpc_id == rpc_id
        assert error.code == code

    def test_create_with_string_rpc_id(self):
        """Should accept string rpc_id."""
        error = JsonRpcError(rpc_id="abc123", code=INVALID_REQUEST)

        assert error.rpc_id == "abc123"

    def test_create_with_none_rpc_id(self):
        """Should accept None rpc_id (for notifications)."""
        error = JsonRpcError(rpc_id=None, code=INVALID_REQUEST)

        assert error.rpc_id is None


@pytest.mark.unit
class TestJsonRpcErrorSerialization:
    """Test JsonRpcError.as_dict() serialization."""

    def test_as_dict_basic_structure(self):
        """Should return dict with jsonrpc, id, and error fields."""
        error = JsonRpcError(rpc_id=1, code=INVALID_REQUEST)
        result = error.as_dict()

        assert "jsonrpc" in result
        assert result["jsonrpc"] == "2.0"
        assert "id" in result
        assert result["id"] == 1
        assert "error" in result
        assert isinstance(result["error"], dict)

    def test_as_dict_error_structure(self):
        """Should include code and message in error object."""
        error = JsonRpcError(rpc_id=1, code=PARSE_ERROR)
        result = error.as_dict()

        assert "code" in result["error"]
        assert result["error"]["code"] == PARSE_ERROR
        assert "message" in result["error"]
        assert result["error"]["message"] == RPC_ERRORS[PARSE_ERROR]

    def test_as_dict_with_data(self):
        """Should include data field in error when provided."""
        data = {"context": "test"}
        error = JsonRpcError(rpc_id=1, code=INTERNAL_ERROR, data=data)
        result = error.as_dict()

        assert "data" in result["error"]
        assert result["error"]["data"] == data

    def test_as_dict_without_data(self):
        """Should not include data field when None."""
        error = JsonRpcError(rpc_id=1, code=INTERNAL_ERROR)
        result = error.as_dict()

        # Data field is omitted when None (per JSON-RPC 2.0 spec)
        assert "data" not in result["error"]

    @pytest.mark.parametrize("code", list(RPC_ERRORS.keys()))
    def test_as_dict_all_error_codes_have_messages(self, code):
        """Should have message for every error code."""
        error = JsonRpcError(rpc_id=1, code=code)
        result = error.as_dict()

        assert result["error"]["message"] == RPC_ERRORS[code]


@pytest.mark.unit
class TestJsonRpcErrorMessageEnhancement:
    """Test error message enhancement with context data."""

    def test_method_not_found_with_method_name(self):
        """Should include method name in METHOD_NOT_FOUND error."""
        error = JsonRpcError(
            rpc_id=1, code=METHOD_NOT_FOUND, data={"method": "test_method"}
        )
        result = error.as_dict()

        message = result["error"]["message"]
        assert "Method Not Found" in message
        assert "test_method" in message
        assert message == "Method Not Found: 'test_method'"

    def test_method_not_found_without_method_name(self):
        """Should use basic message when method name not in data."""
        error = JsonRpcError(rpc_id=1, code=METHOD_NOT_FOUND, data={"other": "value"})
        result = error.as_dict()

        assert result["error"]["message"] == "Method Not Found"

    def test_invalid_request_with_version_info(self):
        """Should include version info in INVALID_REQUEST error."""
        error = JsonRpcError(rpc_id=1, code=INVALID_REQUEST, data={"version": "1.0"})
        result = error.as_dict()

        message = result["error"]["message"]
        assert "Invalid JSON-RPC version '1.0'" in message
        assert "expected '2.0'" in message

    @pytest.mark.parametrize("version", ["1.0", "3.0", "2", 2.0, None])
    def test_invalid_request_with_various_versions(self, version):
        """Should handle various invalid version types in error message."""
        error = JsonRpcError(rpc_id=1, code=INVALID_REQUEST, data={"version": version})
        result = error.as_dict()

        message = result["error"]["message"]
        assert "Invalid JSON-RPC version" in message
        assert str(version) in message

    def test_invalid_request_with_field_info(self):
        """Should include field info in INVALID_REQUEST error."""
        field_msg = "Missing required field 'method'"
        error = JsonRpcError(rpc_id=1, code=INVALID_REQUEST, data={"field": field_msg})
        result = error.as_dict()

        message = result["error"]["message"]
        assert "Invalid Request:" in message
        assert field_msg in message

    def test_invalid_params_with_type_info(self):
        """Should include type info in INVALID_PARAMS error."""
        error = JsonRpcError(
            rpc_id=1,
            code=INVALID_PARAMS,
            data={"expected": "dict or list", "actual": "str"},
        )
        result = error.as_dict()

        message = result["error"]["message"]
        assert "Invalid Params" in message
        assert "Expected dict or list" in message
        assert "got str" in message

    @pytest.mark.parametrize(
        "expected,actual",
        [
            ("dict or list", "str"),
            ("dict or list", "int"),
            ("dict or list", "NoneType"),
            ("string", "int"),
        ],
    )
    def test_invalid_params_with_various_types(self, expected, actual):
        """Should format type mismatch errors correctly."""
        error = JsonRpcError(
            rpc_id=1, code=INVALID_PARAMS, data={"expected": expected, "actual": actual}
        )
        result = error.as_dict()

        message = result["error"]["message"]
        assert expected in message
        assert actual in message

    def test_no_enhancement_for_generic_error(self):
        """Should not enhance GENERIC_APPLICATION_ERROR message."""
        error = JsonRpcError(
            rpc_id=1, code=GENERIC_APPLICATION_ERROR, data={"detail": "some error"}
        )
        result = error.as_dict()

        assert result["error"]["message"] == "Application Error"

    def test_no_enhancement_when_data_not_dict(self):
        """Should not enhance message when data is not a dict."""
        error = JsonRpcError(rpc_id=1, code=METHOD_NOT_FOUND, data="string data")
        result = error.as_dict()

        assert result["error"]["message"] == "Method Not Found"


@pytest.mark.unit
class TestJsonRpcErrorStringRepresentation:
    """Test JsonRpcError.__str__() method."""

    def test_str_returns_json_string(self):
        """Should return JSON string representation."""
        error = JsonRpcError(rpc_id=1, code=INVALID_REQUEST)
        result = str(error)

        # Should be valid JSON
        parsed = json.loads(result)
        assert parsed["jsonrpc"] == "2.0"
        assert parsed["id"] == 1
        assert "error" in parsed

    def test_str_matches_as_dict(self):
        """Should serialize to same structure as as_dict()."""
        error = JsonRpcError(rpc_id=42, code=METHOD_NOT_FOUND, data={"method": "test"})

        dict_result = error.as_dict()
        str_result = json.loads(str(error))

        assert dict_result == str_result


@pytest.mark.unit
class TestGenerateErrorResponse:
    """Test generate_error_response() utility function."""

    def test_generate_with_all_params(self):
        """Should generate error response with all parameters."""
        result = generate_error_response(
            rpc_id=1, code=INTERNAL_ERROR, message="Test error", data={"key": "value"}
        )

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 1
        assert result["error"]["code"] == INTERNAL_ERROR
        assert result["error"]["message"] == "Test error"
        assert result["error"]["data"] == {"key": "value"}

    def test_generate_without_data(self):
        """Should generate error response without data parameter."""
        result = generate_error_response(
            rpc_id=2, code=PARSE_ERROR, message="Parse failed"
        )

        assert result["jsonrpc"] == "2.0"
        assert result["id"] == 2
        assert result["error"]["code"] == PARSE_ERROR
        assert result["error"]["message"] == "Parse failed"
        # Data field is omitted when None (per JSON-RPC 2.0 spec)
        assert "data" not in result["error"]

    def test_generate_with_string_rpc_id(self):
        """Should accept string rpc_id."""
        result = generate_error_response(
            rpc_id="abc", code=INVALID_REQUEST, message="Invalid"
        )

        assert result["id"] == "abc"

    def test_generate_with_none_rpc_id(self):
        """Should accept None rpc_id."""
        result = generate_error_response(
            rpc_id=None, code=INVALID_REQUEST, message="Invalid"
        )

        assert result["id"] is None

    @pytest.mark.parametrize("code", list(RPC_ERRORS.keys()))
    def test_generate_with_all_error_codes(self, code):
        """Should generate response for all error codes."""
        result = generate_error_response(rpc_id=1, code=code, message=RPC_ERRORS[code])

        assert result["error"]["code"] == code


@pytest.mark.unit
class TestErrorCodeConstants:
    """Test that all error code constants are defined correctly."""

    def test_parse_error_code(self):
        """PARSE_ERROR should be -32700."""
        assert PARSE_ERROR == -32700

    def test_invalid_request_code(self):
        """INVALID_REQUEST should be -32600."""
        assert INVALID_REQUEST == -32600

    def test_method_not_found_code(self):
        """METHOD_NOT_FOUND should be -32601."""
        assert METHOD_NOT_FOUND == -32601

    def test_invalid_params_code(self):
        """INVALID_PARAMS should be -32602."""
        assert INVALID_PARAMS == -32602

    def test_internal_error_code(self):
        """INTERNAL_ERROR should be -32603."""
        assert INTERNAL_ERROR == -32603

    def test_generic_application_error_code(self):
        """GENERIC_APPLICATION_ERROR should be -32000."""
        assert GENERIC_APPLICATION_ERROR == -32000

    def test_parse_result_error_code(self):
        """PARSE_RESULT_ERROR should be -32701."""
        assert PARSE_RESULT_ERROR == -32701

    def test_all_codes_in_rpc_errors_dict(self):
        """All error codes should be in RPC_ERRORS dictionary."""
        assert PARSE_ERROR in RPC_ERRORS
        assert INVALID_REQUEST in RPC_ERRORS
        assert METHOD_NOT_FOUND in RPC_ERRORS
        assert INVALID_PARAMS in RPC_ERRORS
        assert INTERNAL_ERROR in RPC_ERRORS
        assert GENERIC_APPLICATION_ERROR in RPC_ERRORS
        assert PARSE_RESULT_ERROR in RPC_ERRORS

    def test_rpc_errors_messages(self):
        """RPC_ERRORS should have appropriate messages."""
        assert RPC_ERRORS[PARSE_ERROR] == "Parse Error"
        assert RPC_ERRORS[INVALID_REQUEST] == "Invalid Request"
        assert RPC_ERRORS[METHOD_NOT_FOUND] == "Method Not Found"
        assert RPC_ERRORS[INVALID_PARAMS] == "Invalid Params"
        assert RPC_ERRORS[INTERNAL_ERROR] == "Internal Error"
        assert RPC_ERRORS[GENERIC_APPLICATION_ERROR] == "Application Error"
        assert RPC_ERRORS[PARSE_RESULT_ERROR] == "Error while parsing result"
