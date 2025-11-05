"""Tests for RPC method decorators.

Coverage: permission_required decorator and helper functions.
Target: 95%+ coverage of decorators.py
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from channels_rpc.context import RpcContext
from channels_rpc.decorators import (
    create_rpc_method_wrapper,
    inspect_accepts_context,
    permission_required,
)
from channels_rpc.exceptions import JsonRpcError, JsonRpcErrorCode


@pytest.mark.unit
class TestInspectAcceptsContext:
    """Test inspect_accepts_context() function."""

    def test_function_with_context_parameter(self):
        """Should return True for function with RpcContext parameter."""

        def method_with_context(ctx: RpcContext, value: int) -> int:
            return value * 2

        result = inspect_accepts_context(method_with_context)
        assert result is True

    def test_function_without_context_parameter(self):
        """Should return False for function without RpcContext parameter."""

        def method_without_context(value: int) -> int:
            return value * 2

        result = inspect_accepts_context(method_without_context)
        assert result is False

    def test_function_with_no_parameters(self):
        """Should return False for function with no parameters."""

        def no_params() -> str:
            return "test"

        result = inspect_accepts_context(no_params)
        assert result is False

    def test_method_with_self_and_context(self):
        """Should return True for method with self and RpcContext."""

        class TestClass:
            def method_with_context(self, ctx: RpcContext, value: int) -> int:
                return value * 2

        result = inspect_accepts_context(TestClass.method_with_context)
        assert result is True

    def test_method_with_self_only(self):
        """Should return False for method with only self parameter."""

        class TestClass:
            def method_with_self_only(self) -> str:
                return "test"

        result = inspect_accepts_context(TestClass.method_with_self_only)
        assert result is False

    def test_function_with_unannotated_parameter(self):
        """Should return False for function with unannotated first parameter."""

        def method_without_annotation(ctx, value: int) -> int:
            return value * 2

        result = inspect_accepts_context(method_without_annotation)
        assert result is False

    def test_function_with_wrong_annotation_type(self):
        """Should return False for function with non-RpcContext annotation."""

        def method_wrong_type(ctx: str, value: int) -> int:
            return value * 2

        result = inspect_accepts_context(method_wrong_type)
        assert result is False


@pytest.mark.unit
class TestCreateRpcMethodWrapper:
    """Test create_rpc_method_wrapper() function."""

    def test_create_wrapper_with_context_function(self):
        """Should create wrapper and detect RpcContext parameter."""

        def test_method(ctx: RpcContext, value: int) -> int:
            return value * 2

        wrapper = create_rpc_method_wrapper(
            func=test_method, name="test_method", options={"websocket": True}
        )

        assert wrapper.func is test_method
        assert wrapper.name == "test_method"
        assert wrapper.options == {"websocket": True}
        assert wrapper.accepts_context is True

    def test_create_wrapper_without_context_function(self):
        """Should create wrapper and detect no RpcContext parameter."""

        def test_method(value: int) -> int:
            return value * 2

        wrapper = create_rpc_method_wrapper(
            func=test_method, name="test_method", options={"websocket": True}
        )

        assert wrapper.accepts_context is False

    def test_create_wrapper_with_explicit_accepts_context(self):
        """Should use explicit accepts_context when provided."""

        def test_method(value: int) -> int:
            return value * 2

        # Explicitly set to True even though function doesn't have context
        wrapper = create_rpc_method_wrapper(
            func=test_method,
            name="test_method",
            options={"websocket": True},
            accepts_context=True,
        )

        assert wrapper.accepts_context is True

    def test_wrapper_preserves_function_name(self):
        """Should preserve original function name in wrapper."""

        def my_function(value: int) -> int:
            return value

        wrapper = create_rpc_method_wrapper(
            func=my_function, name="registered_name", options={}
        )

        # __name__ should match original function
        assert wrapper.__name__ == "my_function"


@pytest.mark.unit
class TestPermissionRequired:
    """Test permission_required() decorator."""

    def create_mock_user(self, is_authenticated: bool, permissions: list[str]):
        """Create a mock user object."""
        user = MagicMock()
        user.is_authenticated = is_authenticated
        empty_perms: list[str] = []
        user.has_perms = MagicMock(
            return_value=all(
                perm in permissions
                for perm in empty_perms  # Will be checked by actual call
            )
        )

        # Mock has_perms to check if all requested permissions are in user's permissions
        def has_perms_impl(requested_perms):
            return all(perm in permissions for perm in requested_perms)

        user.has_perms.side_effect = has_perms_impl
        user.username = "testuser"
        return user

    def create_context(self, user=None, rpc_id=1):
        """Create a mock RpcContext with user in scope."""
        consumer = MagicMock()
        consumer.scope = {"user": user} if user else {}
        return RpcContext(
            consumer=consumer,
            method_name="test_method",
            rpc_id=rpc_id,
            is_notification=False,
        )

    def test_successful_authorization_single_permission(self):
        """Should allow execution when user has required permission."""
        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.can_view"]
        )

        @permission_required("myapp.can_view")
        def test_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user)
        result = test_method(ctx)

        assert result == "success"
        user.has_perms.assert_called_once_with(("myapp.can_view",))

    def test_successful_authorization_multiple_permissions(self):
        """Should allow execution when user has all required permissions."""
        user = self.create_mock_user(
            is_authenticated=True,
            permissions=["myapp.can_view", "myapp.can_edit", "myapp.can_delete"],
        )

        @permission_required("myapp.can_view", "myapp.can_edit")
        def test_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user)
        result = test_method(ctx)

        assert result == "success"
        user.has_perms.assert_called_once_with(("myapp.can_view", "myapp.can_edit"))

    def test_authorization_failure_missing_permission(self):
        """Should raise JsonRpcError when user lacks required permission."""
        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.can_view"]
        )

        @permission_required("myapp.can_edit")
        def test_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user, rpc_id=123)

        with pytest.raises(JsonRpcError) as exc_info:
            test_method(ctx)

        error = exc_info.value
        assert error.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert error.rpc_id == 123

    def test_authorization_failure_missing_one_of_multiple_permissions(self):
        """Should raise JsonRpcError when user lacks one required permission."""
        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.can_view"]
        )

        @permission_required("myapp.can_view", "myapp.can_edit")
        def test_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user)

        with pytest.raises(JsonRpcError) as exc_info:
            test_method(ctx)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_unauthenticated_user_raises_error(self):
        """Should raise JsonRpcError for unauthenticated user."""
        user = self.create_mock_user(is_authenticated=False, permissions=[])

        @permission_required("myapp.can_view")
        def test_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user, rpc_id=456)

        with pytest.raises(JsonRpcError) as exc_info:
            test_method(ctx)

        error = exc_info.value
        assert error.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert error.rpc_id == 456

    def test_missing_user_in_scope_raises_error(self):
        """Should raise JsonRpcError when no user in scope."""

        @permission_required("myapp.can_view")
        def test_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=None)

        with pytest.raises(JsonRpcError) as exc_info:
            test_method(ctx)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_decorator_preserves_function_metadata(self):
        """Should preserve function name and docstring."""

        @permission_required("myapp.can_view")
        def test_method(ctx: RpcContext) -> str:
            """Test docstring."""
            return "success"

        assert test_method.__name__ == "test_method"
        assert test_method.__doc__ == "Test docstring."

    def test_decorator_works_with_additional_parameters(self):
        """Should work with methods that have additional parameters."""
        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.can_edit"]
        )

        @permission_required("myapp.can_edit")
        def test_method(ctx: RpcContext, value: int, name: str) -> str:
            return f"{name}: {value * 2}"

        ctx = self.create_context(user=user)
        result = test_method(ctx, 5, "result")

        assert result == "result: 10"

    def test_decorator_works_with_kwargs(self):
        """Should work with methods using keyword arguments."""
        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.can_view"]
        )

        @permission_required("myapp.can_view")
        def test_method(ctx: RpcContext, **kwargs) -> dict:
            return kwargs

        ctx = self.create_context(user=user)
        result = test_method(ctx, key1="value1", key2="value2")

        assert result == {"key1": "value1", "key2": "value2"}

    def test_error_code_is_method_not_found(self):
        """Should use METHOD_NOT_FOUND error code (not PERMISSION_DENIED).

        This is intentional to avoid information disclosure about method existence.
        """
        user = self.create_mock_user(is_authenticated=True, permissions=[])

        @permission_required("myapp.admin")
        def test_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user)

        with pytest.raises(JsonRpcError) as exc_info:
            test_method(ctx)

        # Intentionally uses METHOD_NOT_FOUND to avoid leaking info
        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND
        assert exc_info.value.code != JsonRpcErrorCode.PERMISSION_DENIED


@pytest.mark.unit
@pytest.mark.asyncio
class TestPermissionRequiredAsync:
    """Test permission_required() decorator with async methods."""

    def create_mock_user(self, is_authenticated: bool, permissions: list[str]):
        """Create a mock user object."""
        user = MagicMock()
        user.is_authenticated = is_authenticated

        def has_perms_impl(requested_perms):
            return all(perm in permissions for perm in requested_perms)

        user.has_perms.side_effect = has_perms_impl
        user.username = "asyncuser"
        return user

    def create_context(self, user=None, rpc_id=1):
        """Create a mock RpcContext with user in scope."""
        consumer = MagicMock()
        consumer.scope = {"user": user} if user else {}
        return RpcContext(
            consumer=consumer,
            method_name="async_test_method",
            rpc_id=rpc_id,
            is_notification=False,
        )

    async def test_successful_authorization_async_method(self):
        """Should allow execution of async method when authorized."""
        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.can_view"]
        )

        @permission_required("myapp.can_view")
        async def async_method(ctx: RpcContext) -> str:
            return "async success"

        ctx = self.create_context(user=user)
        result = await async_method(ctx)

        assert result == "async success"

    async def test_authorization_failure_async_method(self):
        """Should raise JsonRpcError for unauthorized async method."""
        user = self.create_mock_user(is_authenticated=True, permissions=[])

        @permission_required("myapp.can_edit")
        async def async_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user)

        with pytest.raises(JsonRpcError) as exc_info:
            await async_method(ctx)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    async def test_unauthenticated_user_async_method(self):
        """Should raise JsonRpcError for unauthenticated async method call."""
        user = self.create_mock_user(is_authenticated=False, permissions=[])

        @permission_required("myapp.can_view")
        async def async_method(ctx: RpcContext) -> str:
            return "success"

        ctx = self.create_context(user=user)

        with pytest.raises(JsonRpcError) as exc_info:
            await async_method(ctx)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    async def test_async_method_with_parameters(self):
        """Should work with async methods that have additional parameters."""
        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.can_process"]
        )

        @permission_required("myapp.can_process")
        async def async_method(ctx: RpcContext, data: dict) -> dict:
            return {"processed": True, **data}

        ctx = self.create_context(user=user)
        result = await async_method(ctx, {"key": "value"})

        assert result == {"processed": True, "key": "value"}

    async def test_async_method_multiple_permissions(self):
        """Should work with async methods requiring multiple permissions."""
        user = self.create_mock_user(
            is_authenticated=True,
            permissions=["myapp.can_view", "myapp.can_edit", "myapp.can_delete"],
        )

        @permission_required("myapp.can_view", "myapp.can_edit", "myapp.can_delete")
        async def async_method(ctx: RpcContext) -> str:
            return "all permissions granted"

        ctx = self.create_context(user=user)
        result = await async_method(ctx)

        assert result == "all permissions granted"


@pytest.mark.unit
class TestPermissionRequiredIntegration:
    """Integration tests for permission_required with actual RPC consumers."""

    def create_mock_user(self, is_authenticated: bool, permissions: list[str]):
        """Create a mock user object."""
        user = MagicMock()
        user.is_authenticated = is_authenticated

        def has_perms_impl(requested_perms):
            return all(perm in permissions for perm in requested_perms)

        user.has_perms.side_effect = has_perms_impl
        user.username = "integrationuser"
        return user

    def test_decorator_stacks_with_rpc_method(self):
        """Should work when stacked with @rpc_method() decorator."""
        from channels_rpc.registry import get_registry
        from tests.conftest import MockRpcConsumer

        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.delete_user"]
        )

        class TestConsumer(MockRpcConsumer):
            pass

        @TestConsumer.rpc_method()
        @permission_required("myapp.delete_user")
        def delete_user(ctx: RpcContext, user_id: int) -> dict:
            return {"deleted": True, "user_id": user_id}

        # Create consumer with authenticated user
        consumer = TestConsumer(scope={"type": "websocket", "user": user})

        # Get the registered method from registry
        registry = get_registry()
        method_wrapper = registry.get_method(TestConsumer, "delete_user")
        assert method_wrapper is not None

        # Create context
        ctx = RpcContext(
            consumer=consumer,
            method_name="delete_user",
            rpc_id=1,
            is_notification=False,
        )

        # Call through the wrapper
        result = method_wrapper.func(ctx, user_id=123)
        assert result == {"deleted": True, "user_id": 123}

    def test_decorator_denies_without_permission(self):
        """Should deny access when user lacks permission."""
        from channels_rpc.registry import get_registry
        from tests.conftest import MockRpcConsumer

        user = self.create_mock_user(
            is_authenticated=True, permissions=["myapp.view_user"]
        )

        class TestConsumer(MockRpcConsumer):
            pass

        @TestConsumer.rpc_method()
        @permission_required("myapp.delete_user")
        def delete_user(ctx: RpcContext, user_id: int) -> dict:
            return {"deleted": True, "user_id": user_id}

        consumer = TestConsumer(scope={"type": "websocket", "user": user})

        # Get the registered method from registry
        registry = get_registry()
        method_wrapper = registry.get_method(TestConsumer, "delete_user")
        assert method_wrapper is not None

        ctx = RpcContext(
            consumer=consumer,
            method_name="delete_user",
            rpc_id=1,
            is_notification=False,
        )

        with pytest.raises(JsonRpcError) as exc_info:
            method_wrapper.func(ctx, user_id=123)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND

    def test_decorator_with_unauthenticated_user(self):
        """Should deny access for unauthenticated users."""
        from channels_rpc.registry import get_registry
        from tests.conftest import MockRpcConsumer

        user = self.create_mock_user(is_authenticated=False, permissions=[])

        class TestConsumer(MockRpcConsumer):
            pass

        @TestConsumer.rpc_method()
        @permission_required("myapp.view_data")
        def view_data(ctx: RpcContext) -> dict:
            return {"data": "secret"}

        consumer = TestConsumer(scope={"type": "websocket", "user": user})

        # Get the registered method from registry
        registry = get_registry()
        method_wrapper = registry.get_method(TestConsumer, "view_data")
        assert method_wrapper is not None

        ctx = RpcContext(
            consumer=consumer,
            method_name="view_data",
            rpc_id=1,
            is_notification=False,
        )

        with pytest.raises(JsonRpcError) as exc_info:
            method_wrapper.func(ctx)

        assert exc_info.value.code == JsonRpcErrorCode.METHOD_NOT_FOUND
