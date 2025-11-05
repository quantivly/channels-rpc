"""RPC execution context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from channels_rpc.rpc_base import RpcBase


@dataclass
class RpcContext:
    """Context for RPC method execution.

    Provides access to the consumer and request metadata during RPC method execution.
    This replaces the legacy **kwargs consumer injection with an explicit, type-safe
    parameter.

    Attributes
    ----------
    consumer : RpcBase
        The consumer handling this RPC request.
    method_name : str
        Name of the RPC method being called.
    rpc_id : str | int | None
        Request ID from the JSON-RPC call. None for notifications.
    is_notification : bool
        Whether this is a notification (no response expected).

    Examples
    --------
    >>> @MyConsumer.rpc_method()
    >>> def my_method(ctx: RpcContext, param1: str) -> str:
    ...     # Type-safe access to consumer
    ...     session = ctx.scope.get("session", {})
    ...     # Access request metadata
    ...     logger.info(f"Method {ctx.method_name} called with id {ctx.rpc_id}")
    ...     return f"Hello {param1}"

    >>> @MyConsumer.rpc_notification()
    >>> def my_notification(ctx: RpcContext, message: str) -> None:
    ...     # Notifications don't have an ID
    ...     assert ctx.is_notification
    ...     assert ctx.rpc_id is None
    ...     logger.info(f"Received notification: {message}")
    """

    consumer: RpcBase
    method_name: str
    rpc_id: str | int | None
    is_notification: bool

    @property
    def scope(self) -> dict[str, Any]:
        """Get the Django Channels scope from the consumer.

        The scope dict contains connection metadata such as:
        - client: (host, port) tuple
        - headers: Request headers
        - cookies: Request cookies
        - session: Django session (if available)
        - user: Authenticated user (if available)

        Returns
        -------
        dict[str, Any]
            The scope dict containing connection metadata.
        """
        return self.consumer.scope
