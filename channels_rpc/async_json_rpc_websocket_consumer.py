from __future__ import annotations

import json
import logging
from typing import Any

from channels.generic.websocket import AsyncJsonWebsocketConsumer

from channels_rpc.async_rpc_base import AsyncRpcBase
from channels_rpc.exceptions import JsonRpcErrorCode, generate_error_response

logger = logging.getLogger("channels_rpc")


class AsyncJsonRpcWebsocketConsumer(AsyncJsonWebsocketConsumer, AsyncRpcBase):
    """Async WebSocket consumer for JSON-RPC 2.0 communication.
    This consumer provides asynchronous support for handling JSON-RPC 2.0 requests
    over WebSocket connections. Use this class when your RPC methods are async
    functions or when you need to leverage Django Channels' async capabilities
    for better concurrency.

    This class combines Django Channels' AsyncJsonWebsocketConsumer with the
    AsyncRpcBase mixin to provide full async RPC functionality.

    Attributes
    ----------
    json_encoder_class : type[json.JSONEncoder] | None
        Optional custom JSON encoder class for serializing RPC responses.
        If provided, this encoder will be used for all response serialization.
        If None, uses default encoder with str() fallback.

    Use Cases
    ---------
    - When RPC methods need to perform async I/O operations (database, HTTP, etc.)
    - When handling high-concurrency WebSocket connections
    - When integrating with other async Python libraries

    See Also
    --------
    JsonRpcWebsocketConsumer : Synchronous version for sync RPC methods
    AsyncRpcBase : Async RPC base class providing core functionality

    Examples
    --------
    Define an async consumer with async RPC methods::

        from channels_rpc import AsyncJsonRpcWebsocketConsumer

        class MyAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
            @AsyncJsonRpcWebsocketConsumer.rpc_method()
            async def get_data(self, resource_id: int):
                # Async database query
                data = await MyModel.objects.aget(id=resource_id)
                return {"data": data.to_dict()}

            @AsyncJsonRpcWebsocketConsumer.rpc_method()
            async def fetch_external(self, url: str):
                # Async HTTP request
                async with httpx.AsyncClient() as client:
                    response = await client.get(url)
                    return {"content": response.text}
    """

    json_encoder_class: type[json.JSONEncoder] | None = None

    @classmethod
    async def encode_json(cls, data: dict[str, Any]) -> str:  # type: ignore[override]
        """Encode remote procedure call data with custom encoder support.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.

        Returns
        -------
        str
            JSON-encoded string.

        Notes
        -----
        If json_encoder_class is set, uses that encoder. Otherwise uses
        default encoder with str() fallback for non-serializable objects.

        If serialization fails, attempts to send a proper error response.
        As a last resort, returns a hardcoded minimal error to prevent
        connection breakage.

        Examples
        --------
        Use custom encoder for datetime serialization::

            import json
            from datetime import datetime

            class DateTimeEncoder(json.JSONEncoder):
                def default(self, obj):
                    if isinstance(obj, datetime):
                        return obj.isoformat()
                    return super().default(obj)

            class MyAsyncConsumer(AsyncJsonRpcWebsocketConsumer):
                json_encoder_class = DateTimeEncoder
        """
        try:
            if cls.json_encoder_class:
                return json.dumps(data, cls=cls.json_encoder_class)
            return json.dumps(data, default=str)
        except (TypeError, ValueError) as e:
            logger.error("Failed to serialize RPC response: %s", e)

            # Try to send minimal error response
            try:
                error_frame = generate_error_response(
                    rpc_id=data.get("id"),
                    code=JsonRpcErrorCode.PARSE_RESULT_ERROR,
                    message="Failed to serialize result",
                    data=None,  # Don't leak details
                )
                return json.dumps(error_frame)  # This should always work
            except Exception:
                # Last resort - hardcoded minimal error
                logger.exception("Failed to encode error response")
                minimal = (
                    '{"jsonrpc":"2.0","id":null,'
                    '"error":{"code":-32603,"message":"Internal error"}}'
                )
                return minimal

    async def receive(self, text_data=None, bytes_data=None):
        """Override receive to check message size before JSON parsing.

        This prevents DoS attacks where attackers send large JSON payloads
        that consume memory during parsing.

        Parameters
        ----------
        text_data : str | None
            Text data from WebSocket frame
        bytes_data : bytes | None
            Binary data from WebSocket frame
        """
        from channels_rpc.config import get_config

        # Get max message size from config
        max_size = get_config().limits.max_message_size

        # Check size before parsing to prevent DoS
        if text_data:
            size = len(text_data.encode("utf-8"))
        elif bytes_data:
            size = len(bytes_data)
        else:
            size = 0

        if size > max_size:
            error = generate_error_response(
                None,
                JsonRpcErrorCode.REQUEST_TOO_LARGE,
                f"Message size {size} exceeds limit of {max_size} bytes",
            )
            await self.send_json(error)
            return

        # Size is OK, continue with normal JSON parsing
        await super().receive(text_data=text_data, bytes_data=bytes_data)

    async def receive_json(self, content):
        await self._base_receive_json(content)
