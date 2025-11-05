from __future__ import annotations

import json
import logging
from typing import Any

from channels.generic.websocket import JsonWebsocketConsumer

from channels_rpc.exceptions import (
    RPC_ERRORS,
    JsonRpcErrorCode,
    generate_error_response,
)
from channels_rpc.rpc_base import RpcBase

logger = logging.getLogger("channels_rpc")


class JsonRpcWebsocketConsumer(JsonWebsocketConsumer, RpcBase):
    """Synchronous WebSocket consumer for JSON-RPC 2.0 communication.

    Attributes
    ----------
    json_encoder_class : type[json.JSONEncoder] | None
        Optional custom JSON encoder class for serializing RPC responses.
        If provided, this encoder will be used for all response serialization.
        If None, uses default encoder with str() fallback.
    """

    json_encoder_class: type[json.JSONEncoder] | None = None

    def decode_json(self, data: str | bytes | bytearray) -> Any:
        """Decode remote procedure call data.

        Parameters
        ----------
        data : str | bytes | bytearray
            Remote procedure call data.

        Returns
        -------
        Any
            Decoded remote procedure call data.

        Notes
        -----
        Validates message size BEFORE parsing to prevent DoS attacks. If JSON
        parsing fails, sends an error response and returns an empty dict to
        avoid breaking the receive chain.
        """
        from channels_rpc.config import get_config

        # Get max message size from config
        max_size = get_config().limits.max_message_size

        # Check raw message size BEFORE parsing to prevent DoS
        if isinstance(data, bytes):
            size = len(data)
        elif isinstance(data, str):
            size = len(data.encode("utf-8"))
        else:
            size = len(data)

        if size > max_size:
            frame = generate_error_response(
                None,
                JsonRpcErrorCode.REQUEST_TOO_LARGE,
                f"Message size {size} exceeds limit of {max_size} bytes",
            )
            self.send_json(frame)
            return {}

        try:
            return json.loads(data)
        except json.decoder.JSONDecodeError:
            frame = generate_error_response(
                None,
                JsonRpcErrorCode.PARSE_ERROR,
                RPC_ERRORS[JsonRpcErrorCode.PARSE_ERROR],
            )
            self.send_json(frame)
            # Return empty dict to avoid None in receive chain
            # This will be caught by validation as invalid request
            return {}

    def encode_json(self, data: dict[str, Any]) -> str:
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

            class MyConsumer(JsonRpcWebsocketConsumer):
                json_encoder_class = DateTimeEncoder
        """
        try:
            if self.json_encoder_class:
                return json.dumps(data, cls=self.json_encoder_class)
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
                minimal = '{"jsonrpc":"2.0","id":null,"error":{"code":-32603,"message":"Internal error"}}'
                return minimal

    def receive_json(self, data: dict[str, Any]) -> None:
        """Handle incoming JSON messages from the WebSocket.
        This method is called automatically by Django Channels when a JSON message
        is received over the WebSocket connection. It delegates all RPC processing
        to the base class implementation.

        This is a Django Channels lifecycle method and should not be called directly.
        Override this method if you need to intercept or modify messages before
        RPC processing.

        Parameters
        ----------
        data : dict[str, Any]
            Decoded JSON message data from the WebSocket client.
        """
        self._base_receive_json(data)
