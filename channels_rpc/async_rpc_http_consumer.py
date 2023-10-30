import json

from channels.generic.http import AsyncHttpConsumer

from channels_rpc.exceptions import (
    INVALID_REQUEST,
    PARSE_ERROR,
    RPC_ERRORS,
    generate_error_response,
)
from channels_rpc.rpc_base import RpcBase


class AsyncRpcHttpConsumer(AsyncHttpConsumer, RpcBase):
    async def handle(self, body):
        """
        Called on HTTP request
        :param message: message received
        :return:
        """
        if body:
            try:
                data = json.loads(body)
            except ValueError:
                # json could not decoded
                result = generate_error_response(
                    None, PARSE_ERROR, RPC_ERRORS[PARSE_ERROR]
                )
            else:
                result, is_notification = self.intercept_call(data)

            # Set response status code
            # http://www.jsonrpc.org/historical/json-rpc-over-http.html#response-codes
            if is_notification:
                # notification response
                status_code = 204
                if result and "error" in result:
                    status_code = self.RPC_ERROR_TO_HTTP_CODE[result["error"]["code"]]
                result = ""
            elif "error" in result:
                status_code = self.RPC_ERROR_TO_HTTP_CODE[result["error"]["code"]]
            else:
                status_code = 200
        else:
            result = generate_error_response(
                None, INVALID_REQUEST, RPC_ERRORS[INVALID_REQUEST]
            )

        self.send_response(
            status_code,
            json.dumps(result),
            headers=[
                (b"Content-Type", b"application/json-rpc"),
            ],
        )
