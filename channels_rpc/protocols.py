"""Protocol definitions for Django Channels consumer interfaces.

This module defines Protocol classes that specify the interface we expect from
Django Channels consumer classes when using RPC mixins. These protocols enable
proper type checking without creating runtime dependencies on Channels internals.

It also contains shared data structures like RpcMethodWrapper to avoid circular
import issues between modules.
"""

from __future__ import annotations

import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class MethodInfo:
    """Metadata about an RPC method.

    Attributes
    ----------
    name : str
        Method name as registered.
    func : Callable
        The actual function.
    signature : str
        String representation of function signature.
    docstring : str | None
        Method docstring if available.
    accepts_context : bool
        Whether method accepts RpcContext parameter.
    transport_options : dict[str, bool]
        Transport availability (e.g., {"websocket": True}).
    is_notification : bool
        Whether this is a notification handler.
    """

    name: str
    func: Callable
    signature: str
    docstring: str | None
    accepts_context: bool
    transport_options: dict[str, bool]
    is_notification: bool


@dataclass
class RpcMethodWrapper:
    """Wrapper for RPC method with transport options.

    This dataclass wraps RPC methods with metadata about their registration
    and capabilities. It stores the actual function, transport options, method
    name, whether it accepts RpcContext as a parameter, and execution timeout.

    Attributes
    ----------
    func : Callable
        The actual RPC method function.
    options : dict[str, bool]
        Transport options (websocket, http).
    name : str
        Method name to register.
    accepts_context : bool
        Whether method accepts RpcContext as first parameter.
    timeout : float | None
        Maximum execution time in seconds, or None for no timeout.

    Notes
    -----
    The wrapper supports descriptor protocol for proper method binding and
    can be called directly like the wrapped function.
    """

    func: Callable[..., Any]
    options: dict[str, bool]
    name: str
    accepts_context: bool
    timeout: float | None = None

    def __post_init__(self) -> None:
        """Initialize wrapper attributes after dataclass init."""
        # Set __name__ and __qualname__ to mimic the wrapped function
        object.__setattr__(self, "__name__", getattr(self.func, "__name__", self.name))
        object.__setattr__(
            self, "__qualname__", getattr(self.func, "__qualname__", self.name)
        )

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Make the wrapper callable."""
        return self.func(*args, **kwargs)

    def __get__(self, obj: Any, objtype: Any = None) -> Callable[..., Any]:
        """Support instance method binding."""
        if obj is None:
            return self
        return functools.partial(self.__call__, obj)


class ChannelsConsumerProtocol(Protocol):
    """Protocol defining the interface we expect from Channels consumers.

    This protocol defines the methods and attributes that RpcBase mixins
    expect from Django Channels consumer classes. It allows proper type
    checking while maintaining the mixin pattern without runtime overhead.

    Attributes
    ----------
    scope : dict[str, Any]
        ASGI connection scope containing metadata about the connection.
    """

    scope: dict[str, Any]

    def send_json(
        self, content: dict[str, Any], close: bool = False  # noqa: FBT001, FBT002
    ) -> None:
        """Send JSON data to the client.

        Parameters
        ----------
        content : dict[str, Any]
            JSON-serializable dictionary to send.
        close : bool, optional
            Whether to close the connection after sending, by default False.
        """
        ...

    def send(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
        close: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Send text or binary data to the client.

        Parameters
        ----------
        text_data : str | None, optional
            Text data to send, by default None.
        bytes_data : bytes | None, optional
            Binary data to send, by default None.
        close : bool, optional
            Whether to close the connection after sending, by default False.
        """
        ...

    def encode_json(self, content: dict[str, Any]) -> str:
        """Encode a dict as JSON.

        Parameters
        ----------
        content : dict[str, Any]
            Dictionary to encode as JSON.

        Returns
        -------
        str
            JSON-encoded string.
        """
        ...


class AsyncChannelsConsumerProtocol(Protocol):
    """Async protocol for Channels consumers.

    This protocol defines the async interface for Channels consumer classes
    when using async RPC mixins. All methods that involve I/O are async.

    Attributes
    ----------
    scope : dict[str, Any]
        ASGI connection scope containing metadata about the connection.
    """

    scope: dict[str, Any]

    async def send_json(
        self, content: dict[str, Any], close: bool = False  # noqa: FBT001, FBT002
    ) -> None:
        """Send JSON data to the client asynchronously.

        Parameters
        ----------
        content : dict[str, Any]
            JSON-serializable dictionary to send.
        close : bool, optional
            Whether to close the connection after sending, by default False.
        """
        ...

    async def send(
        self,
        text_data: str | None = None,
        bytes_data: bytes | None = None,
        close: bool = False,  # noqa: FBT001, FBT002
    ) -> None:
        """Send text or binary data to the client asynchronously.

        Parameters
        ----------
        text_data : str | None, optional
            Text data to send, by default None.
        bytes_data : bytes | None, optional
            Binary data to send, by default None.
        close : bool, optional
            Whether to close the connection after sending, by default False.
        """
        ...

    def encode_json(self, content: dict[str, Any]) -> str:
        """Encode a dict as JSON.

        Parameters
        ----------
        content : dict[str, Any]
            Dictionary to encode as JSON.

        Returns
        -------
        str
            JSON-encoded string.
        """
        ...
