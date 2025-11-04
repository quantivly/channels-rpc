"""Tests for method registry."""

import gc
import weakref

from channels_rpc.context import RpcContext
from channels_rpc.registry import MethodRegistry, get_registry
from channels_rpc.rpc_base import RpcBase, RpcMethodWrapper


class TestMethodRegistry:
    """Test MethodRegistry class."""

    def test_register_and_get_method(self):
        """Should register and retrieve methods."""
        registry = MethodRegistry()

        class TestClass:
            pass

        wrapper = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="test",
            accepts_context=False,
        )

        registry.register_method(TestClass, "test", wrapper)
        retrieved = registry.get_method(TestClass, "test")
        assert retrieved == wrapper
        assert retrieved.name == "test"

    def test_register_and_get_notification(self):
        """Should register and retrieve notifications."""
        registry = MethodRegistry()

        class TestClass:
            pass

        wrapper = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="notify",
            accepts_context=False,
        )

        registry.register_notification(TestClass, "notify", wrapper)
        retrieved = registry.get_notifications(TestClass)
        assert "notify" in retrieved
        assert retrieved["notify"] == wrapper

    def test_get_methods_returns_dict(self):
        """Should return all methods as a dictionary."""
        registry = MethodRegistry()

        class TestClass:
            pass

        wrapper1 = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="method1",
            accepts_context=False,
        )
        wrapper2 = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="method2",
            accepts_context=False,
        )

        registry.register_method(TestClass, "method1", wrapper1)
        registry.register_method(TestClass, "method2", wrapper2)

        methods = registry.get_methods(TestClass)
        assert len(methods) == 2
        assert "method1" in methods
        assert "method2" in methods

    def test_get_nonexistent_method(self):
        """Should return None for non-existent method."""
        registry = MethodRegistry()

        class TestClass:
            pass

        result = registry.get_method(TestClass, "nonexistent")
        assert result is None

    def test_get_methods_empty_class(self):
        """Should return empty dict for class with no methods."""
        registry = MethodRegistry()

        class TestClass:
            pass

        methods = registry.get_methods(TestClass)
        assert methods == {}

    def test_has_method_true(self):
        """Should return True when method exists."""
        registry = MethodRegistry()

        class TestClass:
            pass

        wrapper = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="test",
            accepts_context=False,
        )

        registry.register_method(TestClass, "test", wrapper)
        assert registry.has_method(TestClass, "test") is True

    def test_has_method_false(self):
        """Should return False when method doesn't exist."""
        registry = MethodRegistry()

        class TestClass:
            pass

        assert registry.has_method(TestClass, "test") is False

    def test_list_method_names(self):
        """Should list all method names."""
        registry = MethodRegistry()

        class TestClass:
            pass

        wrapper1 = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="method1",
            accepts_context=False,
        )
        wrapper2 = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="method2",
            accepts_context=False,
        )

        registry.register_method(TestClass, "method1", wrapper1)
        registry.register_method(TestClass, "method2", wrapper2)

        names = registry.list_method_names(TestClass)
        assert len(names) == 2
        assert "method1" in names
        assert "method2" in names

    def test_list_method_names_empty(self):
        """Should return empty list for class with no methods."""
        registry = MethodRegistry()

        class TestClass:
            pass

        names = registry.list_method_names(TestClass)
        assert names == []

    def test_weak_references(self):
        """Should allow garbage collection of unused classes."""
        registry = MethodRegistry()

        class TestClass:
            pass

        wrapper = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="test",
            accepts_context=False,
        )

        # Create a weak reference to track the class
        weak_ref = weakref.ref(TestClass)

        registry.register_method(TestClass, "test", wrapper)
        assert registry.has_method(TestClass, "test")

        # Delete the class
        del TestClass

        # Force garbage collection
        gc.collect()

        # WeakKeyDictionary should have cleaned up
        assert weak_ref() is None

    def test_multiple_classes(self):
        """Should handle multiple classes independently."""
        registry = MethodRegistry()

        class TestClass1:
            pass

        class TestClass2:
            pass

        wrapper1 = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="method1",
            accepts_context=False,
        )
        wrapper2 = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="method2",
            accepts_context=False,
        )

        registry.register_method(TestClass1, "method1", wrapper1)
        registry.register_method(TestClass2, "method2", wrapper2)

        assert registry.has_method(TestClass1, "method1")
        assert not registry.has_method(TestClass1, "method2")
        assert registry.has_method(TestClass2, "method2")
        assert not registry.has_method(TestClass2, "method1")

    def test_overwrite_method(self):
        """Should allow overwriting a method with the same name."""
        registry = MethodRegistry()

        class TestClass:
            pass

        wrapper1 = RpcMethodWrapper(
            func=lambda: 1,
            options={"websocket": True},
            name="test",
            accepts_context=False,
        )
        wrapper2 = RpcMethodWrapper(
            func=lambda: 2,
            options={"websocket": True},
            name="test",
            accepts_context=False,
        )

        registry.register_method(TestClass, "test", wrapper1)
        registry.register_method(TestClass, "test", wrapper2)

        retrieved = registry.get_method(TestClass, "test")
        assert retrieved == wrapper2

    def test_methods_and_notifications_separate(self):
        """Should keep methods and notifications in separate registries."""
        registry = MethodRegistry()

        class TestClass:
            pass

        method_wrapper = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="test",
            accepts_context=False,
        )
        notification_wrapper = RpcMethodWrapper(
            func=lambda: None,
            options={"websocket": True},
            name="test",
            accepts_context=False,
        )

        registry.register_method(TestClass, "test", method_wrapper)
        registry.register_notification(TestClass, "test", notification_wrapper)

        methods = registry.get_methods(TestClass)
        notifications = registry.get_notifications(TestClass)

        assert methods["test"] == method_wrapper
        assert notifications["test"] == notification_wrapper
        assert methods["test"] is not notifications["test"]


class TestGetRegistry:
    """Test get_registry function."""

    def test_returns_singleton(self):
        """Should return the same registry instance."""
        registry1 = get_registry()
        registry2 = get_registry()
        assert registry1 is registry2

    def test_registry_is_method_registry(self):
        """Should return a MethodRegistry instance."""
        registry = get_registry()
        assert isinstance(registry, MethodRegistry)


class TestRegistryIntegration:
    """Test registry integration with RpcBase."""

    def test_decorator_registers_method(self):
        """Should register methods via decorator."""

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_method()
        def test_method():
            return "test"

        registry = get_registry()
        assert registry.has_method(TestConsumer, "test_method")

    def test_decorator_registers_notification(self):
        """Should register notifications via decorator."""

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_notification()
        def test_notification(self):
            pass

        registry = get_registry()
        notifications = registry.get_notifications(TestConsumer)
        assert "test_notification" in notifications

    def test_get_rpc_methods_uses_registry(self):
        """Should use registry for get_rpc_methods."""

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_method()
        def method1(self):
            pass

        @TestConsumer.rpc_method()
        def method2(self):
            pass

        methods = TestConsumer.get_rpc_methods()
        assert "method1" in methods
        assert "method2" in methods
        assert len(methods) == 2

    def test_get_rpc_notifications_uses_registry(self):
        """Should use registry for get_rpc_notifications."""

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_notification()
        def notification1(self):
            pass

        @TestConsumer.rpc_notification()
        def notification2(self):
            pass

        notifications = TestConsumer.get_rpc_notifications()
        assert "notification1" in notifications
        assert "notification2" in notifications
        assert len(notifications) == 2

    def test_inheritance_registers_separately(self):
        """Should register methods for parent and child classes separately."""

        class ParentConsumer(RpcBase):
            pass

        class ChildConsumer(ParentConsumer):
            pass

        @ParentConsumer.rpc_method()
        def parent_method(self):
            pass

        @ChildConsumer.rpc_method()
        def child_method(self):
            pass

        registry = get_registry()
        parent_methods = registry.get_methods(ParentConsumer)
        child_methods = registry.get_methods(ChildConsumer)

        # Parent should only have parent_method
        assert "parent_method" in parent_methods
        assert "child_method" not in parent_methods

        # Child should only have child_method (decorator registers on specific class)
        assert "child_method" in child_methods
        assert "parent_method" not in child_methods

    def test_custom_method_name(self):
        """Should register with custom method name."""

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_method("custom_name")
        def actual_method_name(self):
            pass

        registry = get_registry()
        assert registry.has_method(TestConsumer, "custom_name")
        assert not registry.has_method(TestConsumer, "actual_method_name")

    def test_wrapper_properties_preserved(self):
        """Should preserve RpcMethodWrapper properties in registry."""

        class TestConsumer(RpcBase):
            pass

        @TestConsumer.rpc_method("test", websocket=True)
        def test_method(self, ctx: RpcContext):
            pass

        registry = get_registry()
        wrapper = registry.get_method(TestConsumer, "test")

        assert wrapper is not None
        assert wrapper.name == "test"
        assert wrapper.options["websocket"] is True
        assert wrapper.accepts_context is True  # Has RpcContext parameter
