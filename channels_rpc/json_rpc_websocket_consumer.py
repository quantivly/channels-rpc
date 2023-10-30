from __future__ import annotations

import json
from typing import Any

from channels.generic.websocket import JsonWebsocketConsumer

from channels_rpc.exceptions import (
    PARSE_ERROR,
    PARSE_RESULT_ERROR,
    RPC_ERRORS,
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
            frame = generate_error_response(None, PARSE_ERROR, RPC_ERRORS[PARSE_ERROR])
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
                PARSE_ERROR,
                RPC_ERRORS[PARSE_RESULT_ERROR],
                str(data["result"]),
            )
            return json.dumps(frame)

    def receive_json(self, data: dict[str, Any]) -> None:
        self._base_receive_json(data)
