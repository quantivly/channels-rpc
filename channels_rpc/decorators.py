"""Shared decorator utilities for RPC methods.

This module provides shared functionality for RPC method decorators to eliminate
code duplication and provide a single source of truth for decorator logic.
"""

from __future__ import annotations

import asyncio
import functools
import inspect
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from channels_rpc.exceptions import JsonRpcError, JsonRpcErrorCode

if TYPE_CHECKING:
    from channels_rpc.context import RpcContext

logger = logging.getLogger("channels_rpc")


def inspect_accepts_context(func: Callable) -> bool:
    """Check if function accepts RpcContext as first parameter after self.

    This function inspects the signature of the provided function to determine
    if it accepts RpcContext as its first parameter (excluding 'self' for methods).
    It handles various annotation formats including direct type references, string
    annotations (from __future__.annotations), and runtime annotation objects.

    Parameters
    ----------
    func : Callable
        Function to inspect for RpcContext parameter.

    Returns
    -------
    bool
        True if function accepts RpcContext as first parameter (after self).
        False if inspection fails or no RpcContext parameter found.

    Notes
    -----
    This function is designed to never raise exceptions. If inspection fails
    for any reason, it returns False and logs a debug message.

    Examples
    --------
    >>> def method_with_context(ctx: RpcContext, value: int) -> int:
    ...     return value * 2
    >>> inspect_accepts_context(method_with_context)
    True

    >>> def method_without_context(value: int) -> int:
    ...     return value * 2
    >>> inspect_accepts_context(method_without_context)
    False
    """
    try:
        sig = inspect.signature(func)
        params = list(sig.parameters.values())

        # Skip 'self' parameter if present (for methods vs free functions)
        first_param_idx = 1 if (params and params[0].name == "self") else 0

        if len(params) <= first_param_idx:
            # No parameters after self (or no parameters at all)
            return False

        first_param = params[first_param_idx]

        # Parameter must have a type annotation
        if first_param.annotation is inspect.Parameter.empty:
            return False

        # Check if annotation is RpcContext
        # This handles multiple cases:
        # 1. Direct type reference: annotation is RpcContext
        # 2. String annotation: annotation == "RpcContext"
        # 3. Runtime annotation object: annotation.__name__ == "RpcContext"
        annotation = first_param.annotation
        if (
            annotation.__class__.__name__ == "RpcContext"
            or annotation == "RpcContext"
            or getattr(annotation, "__name__", "") == "RpcContext"
        ):
            return True

        # Import RpcContext for direct comparison at runtime
        # Inside try block to avoid circular imports at module load
        try:
            from channels_rpc.context import RpcContext

            if annotation is RpcContext:
                return True
        except ImportError:
            pass

        return False

    except (AttributeError, TypeError, ValueError) as e:
        # Log specific errors but don't fail
        logger.debug(
            "Failed to inspect function %s for RpcContext parameter: %s",
            getattr(func, "__name__", "<unknown>"),
            e,
        )
        return False
    except Exception as e:
        # Catch any unexpected errors to prevent decorator failures
        logger.warning(
            "Unexpected error inspecting function %s: %s",
            getattr(func, "__name__", "<unknown>"),
            e,
            exc_info=True,
        )
        return False


def create_rpc_method_wrapper(
    func: Callable,
    name: str,
    options: dict[str, bool],
    *,
    accepts_context: bool | None = None,
    timeout: float | None = None,
) -> Any:  # Returns RpcMethodWrapper but avoid circular import
    """Create an RpcMethodWrapper with proper introspection.

    This is a factory function that creates RpcMethodWrapper instances with
    cached introspection results. It provides a centralized place for wrapper
    creation to ensure consistency across all decorator types.

    Parameters
    ----------
    func : Callable
        The function to wrap.
    name : str
        The RPC method name to register.
    options : dict[str, bool]
        Options for the method (e.g., {"websocket": True}).
    accepts_context : bool | None, optional
        Whether the function accepts RpcContext. If None, will be auto-detected
        using inspect_accepts_context(). Default is None.
    timeout : float | None, optional
        Maximum execution time in seconds. If None, uses default timeout.
        Default is None.

    Returns
    -------
    RpcMethodWrapper
        Wrapper instance configured for the provided function.

    Notes
    -----
    If accepts_context is not explicitly provided, it will be determined by
    inspecting the function signature. Providing it explicitly avoids redundant
    inspection when the caller has already determined this.

    Examples
    --------
    >>> def my_method(ctx: RpcContext, value: int) -> int:
    ...     return value * 2
    >>> wrapper = create_rpc_method_wrapper(
    ...     my_method,
    ...     "my_method",
    ...     {"websocket": True}
    ... )
    >>> wrapper.accepts_context
    True
    """
    # Import here to avoid circular dependency at module load time
    from channels_rpc.protocols import RpcMethodWrapper

    # Auto-detect context acceptance if not provided
    if accepts_context is None:
        accepts_context = inspect_accepts_context(func)

    return RpcMethodWrapper(
        func=func,
        options=options,
        name=name,
        accepts_context=accepts_context,
        timeout=timeout,
    )


def permission_required(*permissions: str) -> Callable:
    """Decorator to require Django permissions for an RPC method.

    This decorator checks that the authenticated user has all specified
    permissions before executing the RPC method. If the user is not
    authenticated or lacks permissions, raises JsonRpcError.

    Parameters
    ----------
    *permissions : str
        One or more permission strings (e.g., 'myapp.can_manage_users').

    Returns
    -------
    Callable
        Decorator function.

    Raises
    ------
    JsonRpcError
        If user is not authenticated or lacks required permissions.

    Examples
    --------
    Require single permission::

        @MyConsumer.rpc_method()
        @permission_required('myapp.delete_user')
        def delete_user(ctx: RpcContext, user_id: int):
            User.objects.get(id=user_id).delete()
            return {"deleted": True}

    Require multiple permissions::

        @MyConsumer.rpc_method()
        @permission_required('myapp.view_reports', 'myapp.export_data')
        def export_report(ctx: RpcContext, report_id: int):
            # User must have both permissions
            ...

    Works with async methods::

        @MyConsumer.rpc_method()
        @permission_required('myapp.admin')
        async def admin_action(ctx: RpcContext):
            await async_admin_operation()

    Notes
    -----
    - Must be used AFTER @rpc_method() decorator (applied second)
    - Requires Django authentication middleware in scope
    - Returns METHOD_NOT_FOUND error (not auth error) to avoid leaking info

    .. versionadded:: 1.0.0
       Added permission decorator for access control.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def sync_wrapper(ctx: RpcContext, *args: Any, **kwargs: Any) -> Any:
            # Extract user from context
            user = ctx.scope.get("user")

            # Check authentication
            if not user or not getattr(user, "is_authenticated", False):
                raise JsonRpcError(
                    rpc_id=ctx.rpc_id,
                    code=JsonRpcErrorCode.METHOD_NOT_FOUND,  # Don't reveal existence
                )

            # Check permissions
            if not user.has_perms(permissions):
                logger.warning(
                    "User %s lacks permissions %s for method %s",
                    getattr(user, "username", "unknown"),
                    permissions,
                    ctx.method_name,
                )
                raise JsonRpcError(
                    rpc_id=ctx.rpc_id,
                    code=JsonRpcErrorCode.METHOD_NOT_FOUND,  # Don't reveal existence
                )

            return func(ctx, *args, **kwargs)

        @functools.wraps(func)
        async def async_wrapper(ctx: RpcContext, *args: Any, **kwargs: Any) -> Any:
            user = ctx.scope.get("user")

            if not user or not getattr(user, "is_authenticated", False):
                raise JsonRpcError(
                    rpc_id=ctx.rpc_id,
                    code=JsonRpcErrorCode.METHOD_NOT_FOUND,
                )

            if not user.has_perms(permissions):
                logger.warning(
                    "User %s lacks permissions %s for method %s",
                    getattr(user, "username", "unknown"),
                    permissions,
                    ctx.method_name,
                )
                raise JsonRpcError(
                    rpc_id=ctx.rpc_id,
                    code=JsonRpcErrorCode.METHOD_NOT_FOUND,
                )

            return await func(ctx, *args, **kwargs)

        # Return appropriate wrapper based on whether func is async
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
