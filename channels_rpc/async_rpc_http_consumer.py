import json

from channels.generic.http import AsyncHttpConsumer

from channels_rpc.async_rpc_base import AsyncRpcBase
from channels_rpc.exceptions import (
    INVALID_REQUEST,
    PARSE_ERROR,
    RPC_ERRORS,
    generate_error_response,
)


class AsyncRpcHttpConsumer(AsyncHttpConsumer, AsyncRpcBase):
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
                is_notification = False
            else:
                result, is_notification = await self.intercept_call(data)

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
            status_code = 400

        await self.send_response(
            status_code,
            json.dumps(result),
            headers=[
                (b"Content-Type", b"application/json-rpc"),
            ],
        )
