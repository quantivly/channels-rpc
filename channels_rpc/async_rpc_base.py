from __future__ import annotations

import json
import logging
from collections.abc import Callable
from inspect import getfullargspec
from typing import Any

from django.conf import settings

from channels_rpc.exceptions import (
    GENERIC_APPLICATION_ERROR,
    RPC_ERRORS,
    JsonRpcError,
    generate_error_response,
)
from channels_rpc.rpc_base import RpcBase
from channels_rpc.utils import create_json_rpc_frame

logger = logging.getLogger(__name__)


class AsyncRpcBase(RpcBase):
    async def __get_result(self, method: Callable, params: dict | list) -> Any:
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

    async def __process(self, data: dict[str, Any], *, is_notification: bool = False):
        method = self._get_method(data, is_notification=is_notification)
        params = self._get_params(data)
        if settings.DEBUG:
            logger.debug(f"Executing {method.__qualname__}({json.dumps(params)})")
        result = await self.__get_result(method, params)
        # check and pack result
        if not is_notification:
            if settings.DEBUG:
                logger.debug("Execution result: %s", result)
            result = create_json_rpc_frame(result=result, rpc_id=data.get("id"))
        elif result is not None:
            logger.warning("The notification method shouldn't return any result")
            logger.warning(f"method: {method.__qualname__}, params: {params}")
            result = None
        return result

    async def _handle(self, data):
        result = None
        is_notification = False
        if data is None:
            message = RPC_ERRORS[self.INVALID_REQUEST]
            result = generate_error_response(
                rpc_id=None, code=self.INVALID_REQUEST, message=message
            )
        elif isinstance(data, dict):
            method_name = data.get("method")
            rpc_id = data.get("id")
            try:
                is_notification = method_name is not None and rpc_id is None
                result = await self.__process(data, is_notification=is_notification)
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
        elif isinstance(data, list):
            # TODO: implement batch calls
            invalid_calls = [x for x in data if not isinstance(x, dict)]
            if invalid_calls:
                message = RPC_ERRORS[self.INVALID_REQUEST]
                result = generate_error_response(
                    rpc_id=None, code=self.INVALID_REQUEST, message=message
                )
        return result, is_notification

    async def _base_receive_json(self, data: dict[str, Any]) -> None:
        result, is_notification = await self._handle(data)
        if not is_notification:
            await self.send_json(result)
