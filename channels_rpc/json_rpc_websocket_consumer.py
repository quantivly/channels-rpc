from __future__ import annotations

import json
from typing import Any

from channels.generic.websocket import JsonWebsocketConsumer

from channels_rpc.exceptions import (
    RPC_ERRORS,
    JsonRpcErrorCode,
    generate_error_response,
)
from channels_rpc.rpc_base import RpcBase


class JsonRpcWebsocketConsumer(JsonWebsocketConsumer, RpcBase):
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
        """
        try:
            return json.loads(data)
        except json.decoder.JSONDecodeError:
            frame = generate_error_response(
                None,
                JsonRpcErrorCode.PARSE_ERROR,
                RPC_ERRORS[JsonRpcErrorCode.PARSE_ERROR],
            )
            self.send_json(frame)

    def encode_json(self, data: dict[str, Any]) -> str:
        """Encode remote procedure call data.

        Parameters
        ----------
        data : dict[str, Any]
            Remote procedure call data.

        Returns
        -------
        str
            Encoded remote procedure call data.
        """
        try:
            return json.dumps(data)
        except TypeError:
            frame = generate_error_response(
                None,
                JsonRpcErrorCode.PARSE_ERROR,
                RPC_ERRORS[JsonRpcErrorCode.PARSE_RESULT_ERROR],
                str(data["result"]),
            )
            return json.dumps(frame)

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
