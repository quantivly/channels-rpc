"""Protocol definitions for Django Channels consumer interfaces.

This module defines Protocol classes that specify the interface we expect from
Django Channels consumer classes when using RPC mixins. These protocols enable
proper type checking without creating runtime dependencies on Channels internals.
"""

from __future__ import annotations

from typing import Any, Protocol


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
