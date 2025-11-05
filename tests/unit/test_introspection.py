"""Tests for RPC method introspection functionality.

This module tests the method introspection API added in version 1.0.0:
- get_method_info() - detailed method metadata
- describe_api() - comprehensive API description
- MethodInfo dataclass - method metadata structure

These tests ensure proper introspection of registered RPC methods and
notifications, including signature extraction, docstring retrieval,
and context parameter detection.
"""

from __future__ import annotations

import inspect

import pytest

from channels_rpc.context import RpcContext
from channels_rpc.protocols import MethodInfo


@pytest.mark.unit
class TestGetMethodInfo:
    """Test get_method_info() classmethod - detailed method metadata retrieval."""

    def test_get_method_info_basic_method(self, consumer_with_methods):
        """Should return MethodInfo for basic method without context."""
        info = consumer_with_methods.__class__.get_method_info("add")

        assert isinstance(info, MethodInfo)
        assert info.name == "add"
        # Signature includes quotes due to __future__.annotations
        assert "a:" in info.signature and "int" in info.signature
        assert "b:" in info.signature
        assert info.accepts_context is False
        assert info.is_notification is False
        assert "websocket" in info.transport_options

    def test_get_method_info_method_with_context(self, consumer_with_methods):
        """Should correctly detect RpcContext parameter."""
        info = consumer_with_methods.__class__.get_method_info("echo")

        assert info.name == "echo"
        assert info.accepts_context is True
        assert "ctx:" in info.signature and "RpcContext" in info.signature
        assert info.is_notification is False

    def test_get_method_info_notification(self, consumer_with_methods):
        """Should return metadata for notification handlers."""
        info = consumer_with_methods.__class__.get_method_info("notify_event")

        assert info.name == "notify_event"
        assert info.is_notification is True
        assert info.accepts_context is False
        assert "event:" in info.signature and "str" in info.signature

    def test_get_method_info_websocket_transport_option(self, consumer_with_methods):
        """Should include transport options in metadata."""
        info = consumer_with_methods.__class__.get_method_info("websocket_only")

        assert info.transport_options["websocket"] is True

    def test_get_method_info_disabled_transport(self, consumer_with_methods):
        """Should reflect disabled transport options."""
        info = consumer_with_methods.__class__.get_method_info("no_websocket")

        assert info.transport_options["websocket"] is False

    def test_get_method_info_includes_docstring(self, mock_websocket_scope):
        """Should extract docstring from method."""
        from channels_rpc.rpc_base import RpcBase

        class ConsumerWithDocs(RpcBase):
            def __init__(self, scope):
                self.scope = scope
                self.sent_messages = []

            def send_json(self, data):  # type: ignore[override]
                self.sent_messages.append(data)

            def send(self, data):  # type: ignore[override]
                self.sent_messages.append(data)

            def encode_json(self, data):
                import json

                return json.dumps(data)

        @ConsumerWithDocs.rpc_method()
        def documented_method(value: int) -> int:
            """This method is well documented.

            Parameters
            ----------
            value : int
                Input value.

            Returns
            -------
            int
                Doubled value.
            """
            return value * 2

        info = ConsumerWithDocs.get_method_info("documented_method")

        assert info.docstring is not None
        assert "well documented" in info.docstring
        assert "Parameters" in info.docstring

    def test_get_method_info_missing_docstring(self, consumer_with_methods):
        """Should return None for methods without docstrings."""
        info = consumer_with_methods.__class__.get_method_info("add")

        # add() has no docstring in the fixture
        assert info.docstring is None

    def test_get_method_info_raises_keyerror_for_unknown_method(
        self, consumer_with_methods
    ):
        """Should raise KeyError if method is not registered."""
        with pytest.raises(KeyError) as exc_info:
            consumer_with_methods.__class__.get_method_info("unknown_method")

        assert "unknown_method" in str(exc_info.value)
        assert "not registered" in str(exc_info.value)

    def test_get_method_info_callable_attribute(self, consumer_with_methods):
        """Should include callable func attribute in MethodInfo."""
        info = consumer_with_methods.__class__.get_method_info("add")

        assert callable(info.func)
        # Can call the function directly through the metadata
        result = info.func(2, 3)
        assert result == 5

    def test_get_method_info_preserves_signature_object(self, consumer_with_methods):
        """Should return signature as string for JSON serialization."""
        info = consumer_with_methods.__class__.get_method_info("add")

        # Signature should be a string, not inspect.Signature object
        assert isinstance(info.signature, str)
        # Should contain parameter information
        assert "a:" in info.signature
        assert "b:" in info.signature
        assert "int" in info.signature


@pytest.mark.unit
class TestDescribeApi:
    """Test describe_api() classmethod - comprehensive API description."""

    def test_describe_api_structure(self, consumer_with_methods):
        """Should return properly structured API description."""
        api_desc = consumer_with_methods.__class__.describe_api()

        assert "jsonrpc" in api_desc
        assert api_desc["jsonrpc"] == "2.0"
        assert "consumer" in api_desc
        assert "methods" in api_desc
        assert "notifications" in api_desc
        assert isinstance(api_desc["methods"], list)
        assert isinstance(api_desc["notifications"], list)

    def test_describe_api_includes_consumer_name(self, consumer_with_methods):
        """Should include consumer class name in description."""
        api_desc = consumer_with_methods.__class__.describe_api()

        assert api_desc["consumer"] == "TestConsumer"

    def test_describe_api_lists_all_methods(self, consumer_with_methods):
        """Should include all registered methods."""
        api_desc = consumer_with_methods.__class__.describe_api()
        method_names = {m["name"] for m in api_desc["methods"]}

        # From consumer_with_methods fixture
        assert "add" in method_names
        assert "echo" in method_names
        assert "websocket_only" in method_names
        assert "no_websocket" in method_names

    def test_describe_api_lists_all_notifications(self, consumer_with_methods):
        """Should include all registered notifications."""
        api_desc = consumer_with_methods.__class__.describe_api()
        notification_names = {n["name"] for n in api_desc["notifications"]}

        assert "notify_event" in notification_names

    def test_describe_api_method_has_required_fields(self, consumer_with_methods):
        """Should include all required fields for each method."""
        api_desc = consumer_with_methods.__class__.describe_api()

        # Find the 'add' method
        add_method = next(m for m in api_desc["methods"] if m["name"] == "add")

        assert "name" in add_method
        assert "signature" in add_method
        assert "doc" in add_method
        assert "accepts_context" in add_method
        assert "transports" in add_method

    def test_describe_api_notification_has_required_fields(self, consumer_with_methods):
        """Should include required fields for each notification."""
        api_desc = consumer_with_methods.__class__.describe_api()

        # Find the notification
        notify = next(
            n for n in api_desc["notifications"] if n["name"] == "notify_event"
        )

        assert "name" in notify
        assert "signature" in notify
        assert "doc" in notify
        assert "accepts_context" in notify

    def test_describe_api_includes_signatures(self, consumer_with_methods):
        """Should include method signatures in description."""
        api_desc = consumer_with_methods.__class__.describe_api()

        add_method = next(m for m in api_desc["methods"] if m["name"] == "add")
        # Signature includes type information
        assert "a:" in add_method["signature"]
        assert "b:" in add_method["signature"]
        assert "int" in add_method["signature"]

    def test_describe_api_includes_context_flag(self, consumer_with_methods):
        """Should correctly flag methods that accept context."""
        api_desc = consumer_with_methods.__class__.describe_api()

        add_method = next(m for m in api_desc["methods"] if m["name"] == "add")
        echo_method = next(m for m in api_desc["methods"] if m["name"] == "echo")

        assert add_method["accepts_context"] is False
        assert echo_method["accepts_context"] is True

    def test_describe_api_includes_transport_options(self, consumer_with_methods):
        """Should list available transports for each method."""
        api_desc = consumer_with_methods.__class__.describe_api()

        ws_method = next(
            m for m in api_desc["methods"] if m["name"] == "websocket_only"
        )
        no_ws_method = next(
            m for m in api_desc["methods"] if m["name"] == "no_websocket"
        )

        # websocket_only should list websocket as available
        assert "websocket" in ws_method["transports"]
        # no_websocket should not list websocket
        assert "websocket" not in no_ws_method["transports"]

    def test_describe_api_handles_missing_docstrings(self, consumer_with_methods):
        """Should handle methods without docstrings gracefully."""
        api_desc = consumer_with_methods.__class__.describe_api()

        add_method = next(m for m in api_desc["methods"] if m["name"] == "add")
        # add() has no docstring, should be None
        assert add_method["doc"] is None

    def test_describe_api_with_empty_consumer(self, mock_websocket_scope):
        """Should handle consumer with no registered methods."""
        from channels_rpc.rpc_base import RpcBase

        class EmptyConsumer(RpcBase):
            def __init__(self, scope):
                self.scope = scope

            def send_json(self, data):  # type: ignore[override]
                pass

            def send(self, data):  # type: ignore[override]
                pass

            def encode_json(self, data):
                import json

                return json.dumps(data)

        api_desc = EmptyConsumer.describe_api()

        assert api_desc["methods"] == []
        assert api_desc["notifications"] == []
        assert api_desc["consumer"] == "EmptyConsumer"

    def test_describe_api_json_serializable(self, consumer_with_methods):
        """Should return data that can be JSON serialized."""
        import json

        api_desc = consumer_with_methods.__class__.describe_api()

        # Should not raise
        json_str = json.dumps(api_desc)
        assert isinstance(json_str, str)

        # Should be able to parse it back
        parsed = json.loads(json_str)
        assert parsed["jsonrpc"] == "2.0"

    def test_describe_api_introspection_failures_logged(
        self, mock_websocket_scope, caplog
    ):
        """Should log warnings if introspection fails for a method."""
        from channels_rpc.registry import get_registry
        from channels_rpc.rpc_base import RpcBase

        class BrokenConsumer(RpcBase):
            def __init__(self, scope):
                self.scope = scope

            def send_json(self, data):  # type: ignore[override]
                pass

            def send(self, data):  # type: ignore[override]
                pass

            def encode_json(self, data):
                import json

                return json.dumps(data)

        # Manually register a broken method (without proper wrapper)
        registry = get_registry()
        # Register a non-callable to trigger error
        registry._methods[BrokenConsumer] = {"broken_method": None}

        api_desc = BrokenConsumer.describe_api()

        # Should continue and return partial results
        assert "methods" in api_desc
        # Should have logged a warning
        assert any(
            "Failed to introspect" in record.message for record in caplog.records
        )


@pytest.mark.unit
class TestMethodInfoDataclass:
    """Test MethodInfo dataclass structure and behavior."""

    def test_method_info_dataclass_fields(self):
        """Should have all required fields."""
        # Create a minimal MethodInfo instance
        info = MethodInfo(
            name="test_method",
            func=lambda x: x,
            signature="(x: int) -> int",
            docstring="Test docstring",
            accepts_context=True,
            transport_options={"websocket": True},
            is_notification=False,
        )

        assert info.name == "test_method"
        assert callable(info.func)
        assert info.signature == "(x: int) -> int"
        assert info.docstring == "Test docstring"
        assert info.accepts_context is True
        assert info.transport_options == {"websocket": True}
        assert info.is_notification is False

    def test_method_info_allows_none_docstring(self):
        """Should allow None for docstring when not available."""
        info = MethodInfo(
            name="test",
            func=lambda: None,
            signature="() -> None",
            docstring=None,
            accepts_context=False,
            transport_options={},
            is_notification=False,
        )

        assert info.docstring is None

    def test_method_info_callable_func(self):
        """Should allow calling the function through the dataclass."""

        def add(a, b):
            return a + b

        info = MethodInfo(
            name="add",
            func=add,
            signature="(a, b)",
            docstring=None,
            accepts_context=False,
            transport_options={},
            is_notification=False,
        )

        result = info.func(2, 3)
        assert result == 5


@pytest.mark.unit
class TestIntrospectionWithAsyncMethods:
    """Test introspection works correctly with async methods."""

    def test_get_method_info_async_method(self, async_consumer_with_methods):
        """Should correctly introspect async methods."""
        info = async_consumer_with_methods.__class__.get_method_info("async_add")

        assert info.name == "async_add"
        assert info.accepts_context is False
        assert "a:" in info.signature and "int" in info.signature
        assert "b:" in info.signature

    def test_get_method_info_async_with_context(self, async_consumer_with_methods):
        """Should detect RpcContext in async methods."""
        info = async_consumer_with_methods.__class__.get_method_info("async_echo")

        assert info.accepts_context is True
        assert "ctx:" in info.signature and "RpcContext" in info.signature

    def test_get_method_info_async_notification(self, async_consumer_with_methods):
        """Should introspect async notification handlers."""
        info = async_consumer_with_methods.__class__.get_method_info("async_notify")

        assert info.is_notification is True
        assert "event:" in info.signature and "str" in info.signature

    def test_describe_api_async_consumer(self, async_consumer_with_methods):
        """Should generate API description for async consumer."""
        api_desc = async_consumer_with_methods.__class__.describe_api()

        assert api_desc["consumer"] == "TestAsyncConsumer"
        method_names = {m["name"] for m in api_desc["methods"]}
        assert "async_add" in method_names
        assert "async_echo" in method_names

        notification_names = {n["name"] for n in api_desc["notifications"]}
        assert "async_notify" in notification_names


@pytest.mark.unit
class TestIntrospectionEdgeCases:
    """Test edge cases and error conditions in introspection."""

    def test_get_method_info_checks_methods_first(self, mock_websocket_scope):
        """Should check methods registry before notifications."""
        from channels_rpc.rpc_base import RpcBase

        class TestConsumer(RpcBase):
            def __init__(self, scope):
                self.scope = scope

            def send_json(self, data):  # type: ignore[override]
                pass

            def send(self, data):  # type: ignore[override]
                pass

            def encode_json(self, data):
                import json

                return json.dumps(data)

        @TestConsumer.rpc_method()
        def my_method() -> str:
            return "method"

        info = TestConsumer.get_method_info("my_method")
        assert info.is_notification is False

    def test_get_method_info_checks_notifications_second(self, mock_websocket_scope):
        """Should check notifications if not found in methods."""
        from channels_rpc.rpc_base import RpcBase

        class TestConsumer(RpcBase):
            def __init__(self, scope):
                self.scope = scope

            def send_json(self, data):  # type: ignore[override]
                pass

            def send(self, data):  # type: ignore[override]
                pass

            def encode_json(self, data):
                import json

                return json.dumps(data)

        @TestConsumer.rpc_notification()
        def my_notification() -> None:
            pass

        info = TestConsumer.get_method_info("my_notification")
        assert info.is_notification is True

    def test_get_method_info_with_complex_signature(self, mock_websocket_scope):
        """Should handle complex method signatures correctly."""
        from channels_rpc.rpc_base import RpcBase

        class TestConsumer(RpcBase):
            def __init__(self, scope):
                self.scope = scope

            def send_json(self, data):  # type: ignore[override]
                pass

            def send(self, data):  # type: ignore[override]
                pass

            def encode_json(self, data):
                import json

                return json.dumps(data)

        @TestConsumer.rpc_method()
        def complex_method(
            ctx: RpcContext,
            required: str,
            optional: int = 42,
            *args: str,
            flag: bool = True,
            **kwargs: dict,
        ) -> dict:
            """Complex signature with all parameter types."""
            return {}

        info = TestConsumer.get_method_info("complex_method")

        assert info.accepts_context is True
        sig = info.signature
        assert "required:" in sig and "str" in sig
        assert "optional:" in sig and "int" in sig and "= 42" in sig
        assert "*args:" in sig
        assert "flag:" in sig and "bool" in sig and "= True" in sig
        assert "**kwargs:" in sig and "dict" in sig
