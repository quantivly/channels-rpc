from __future__ import annotations

import json
import logging
from collections.abc import Callable
from inspect import getfullargspec
from typing import Any

from channels_rpc import logs
from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    INVALID_REQUEST,
    RPC_ERRORS,
    JsonRpcError,
    generate_error_response,
)
from channels_rpc.rpc_base import RpcBase

# Removed unused import

logger = logging.getLogger("django.channels.rpc")


class AsyncRpcBase(RpcBase):
    async def execute_called_method(self, method: Callable, params: dict | list) -> Any:
        func_args = getfullargspec(method).varkw
        if func_args and "kwargs" in func_args:
            return (
                await method(*params, consumer=self)
                if isinstance(params, list)
                else await method(**params, consumer=self)
            )
        elif isinstance(params, list):
            return await method(*params)
        else:
            return await method(**params)

    async def process_call(
        self, data: dict[str, Any], *, is_notification: bool = False
    ):
        from channels_rpc.utils import create_json_rpc_response

        method = self.get_method(data, is_notification=is_notification)
        params = self.get_params(data)
        rpc_id, rpc_id_key = self.get_rpc_id(data)
        logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")
        result = await self.execute_called_method(method, params)
        if not is_notification:
            logger.debug("Execution result: %s", result)
            # Return standard JSON-RPC 2.0 response
            response = create_json_rpc_response(
                rpc_id=rpc_id,
                result=result,
                compressed=False,
            )
            return response
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None
        return result

    async def intercept_call(
        self, data: dict[str, Any] | list[str, Any] | None
    ) -> tuple[Any, bool]:
        logger.debug("Intercepting call: %s", data)
        if not data:
            logger.warning(logs.EMPTY_CALL)
            message = RPC_ERRORS[INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=INVALID_REQUEST, message=message
            )
            return result, False

        # Handle JSON-RPC 2.0 and mixed format
        request = None
        rpc_id = None
        method_name = None

        if isinstance(data, dict):
            # Check for mixed format (both "request" and "response" fields)
            if "request" in data and "response" in data:
                logger.debug(f"Received mixed format message: {data}")
                # If both are present, check if this is a response to our request
                if "result" in data.get("response", {}) or "error" in data.get(
                    "response", {}
                ):
                    # This is a response - extract the JSON-RPC 2.0 response part
                    response_data = data["response"]
                    # Convert legacy response to JSON-RPC 2.0 format
                    rpc_response = {
                        "jsonrpc": "2.0",
                        "id": response_data.get("call_id"),
                        "result": response_data.get("result"),
                    }
                    logger.debug(f"Extracted RPC response: {rpc_response}")
                    return rpc_response, True
                else:
                    # This is a request - extract the request part
                    request_data = data["request"]
                    logger.debug(f"Extracted RPC request: {request_data}")
                    rpc_id = request_data.get("call_id") or request_data.get("id")
                    method_name = request_data.get("method")
                    params = request_data.get("arguments", {})

                    # Build request object for backward compatibility with jsonrpc field
                    request = {
                        "method": method_name,
                        "arguments": params
                        if isinstance(params, dict)
                        else {"params": params},
                        "id": rpc_id,
                        "jsonrpc": "2.0",  # Add JSON-RPC version for validation
                    }

            # Check if this is a pure JSON-RPC 2.0 response
            elif "result" in data or "error" in data:
                logger.debug(f"Received pure JSON-RPC 2.0 response: {data}")
                return data, True

            # Check if this is a pure JSON-RPC 2.0 request
            elif "method" in data:
                logger.debug(f"Received pure JSON-RPC 2.0 request: {data}")
                rpc_id = data.get("id")
                method_name = data.get("method")
                params = data.get("params", {})

                # For pure JSON-RPC 2.0 requests, keep format but add arguments field
                request = {
                    "method": method_name,
                    "arguments": params
                    if isinstance(params, dict)
                    else {"params": params},
                    "id": rpc_id,
                    "jsonrpc": "2.0",  # Preserve JSON-RPC version for validation
                }
            else:
                # Not a recognized format
                logger.warning(f"Unrecognized message format: {data}")
                message = RPC_ERRORS[INVALID_REQUEST]
                result = generate_error_response(
                    rpc_id=None, code=INVALID_REQUEST, message=message
                )
                return result, False

        # Ensure we have a valid request to process
        if request is None:
            logger.warning(f"No valid request could be extracted from: {data}")
            message = RPC_ERRORS[INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=INVALID_REQUEST, message=message
            )
            return result, False

        # Continue processing the request
        is_notification = rpc_id is None
        logger.debug(logs.CALL_INTERCEPTED, request)

        if rpc_id:
            logger.info(logs.RPC_METHOD_CALL_START, method_name, rpc_id)
        else:
            logger.info(logs.RPC_NOTIFICATION_START, method_name)

        try:
            result = await self.process_call(request, is_notification=is_notification)
        except JsonRpcError as e:
            result = e.as_dict()
        except Exception as e:
            logger.debug("Application error: %s", e)
            exception_data = e.args[0] if len(e.args) == 1 else e.args
            result = generate_error_response(
                rpc_id=rpc_id,
                code=GENERIC_APPLICATION_ERROR,
                message=str(e),
                data=exception_data,
            )

        if rpc_id:
            logger.debug(logs.RPC_METHOD_CALL_END, rpc_id, method_name, result)
        else:
            logger.debug(logs.RPC_NOTIFICATION_END, method_name)

        return result, is_notification

    async def _base_receive_json(self, data: dict[str, Any]) -> None:
        logger.debug("Received JSON: %s", data)
        result, is_notification = await self.intercept_call(data)
        if not is_notification:
            logger.debug("Sending result: %s", result)
            await self.send_json(result)
