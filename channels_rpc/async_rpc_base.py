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
from channels_rpc.utils import create_json_rpc_frame

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
        method = self.get_method(data, is_notification=is_notification)
        params = self.get_params(data)
        rpc_id_key = "id"
        if rpc_id_key in data:
            rpc_id = data[rpc_id_key]
        elif "call_id" in data:
            rpc_id = data["call_id"]
            rpc_id_key = "call_id"
        logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")
        result = await self.execute_called_method(method, params)
        if not is_notification:
            logger.debug("Execution result: %s", result)
            result = create_json_rpc_frame(
                result=result,
                rpc_id=rpc_id,
                rpc_id_key=rpc_id_key,
                method=method,
                params=params,
            )
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None
        return result

    async def intercept_call(
        self, data: dict[str, Any] | list[str, Any] | None
    ) -> tuple[Any, bool]:
        result: Any = None
        is_notification: bool = False
        if isinstance(data, dict) and "request" in data:
            data = data["request"]
        logger.debug(logs.CALL_INTERCEPTED, data)
        if data is None:
            logger.warning(logs.EMPTY_CALL)
            message = RPC_ERRORS[INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=INVALID_REQUEST, message=message
            )
        elif isinstance(data, dict):
            method_name = data.get("method")
            rpc_id = data.get("id") or data.get("call_id")
            is_notification = method_name is not None and rpc_id is None
            if rpc_id:
                logger.info(logs.RPC_METHOD_CALL_START, method_name, rpc_id)
            else:
                logger.info(logs.RPC_NOTIFICATION_START, method_name)
            try:
                result = await self.process_call(data, is_notification=is_notification)
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
        # elif isinstance(data, list):
        #     # TODO: implement batch calls
        #     invalid_calls = [x for x in data if not isinstance(x, dict)]
        #     if invalid_calls:
        #         message = RPC_ERRORS[INVALID_REQUEST]
        #         result = generate_error_response(
        #             rpc_id=None, code=INVALID_REQUEST, message=message
        #         )
        if rpc_id:
            logger.debug(logs.RPC_METHOD_CALL_END, rpc_id, method_name, result)
        else:
            logger.debug(logs.RPC_NOTIFICATION_END, method_name)
        return result, is_notification

    async def _base_receive_json(self, data: dict[str, Any]) -> None:
        result, is_notification = await self.intercept_call(data)
        if not is_notification:
            logger.debug("Sending result: %s", result)
            await self.send_json(result)
