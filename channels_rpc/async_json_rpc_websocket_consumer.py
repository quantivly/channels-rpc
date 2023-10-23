from channels.generic.websocket import AsyncJsonWebsocketConsumer

from channels_rpc.async_rpc_base import AsyncRpcBase


class AsyncJsonRpcWebsocketConsumer(AsyncJsonWebsocketConsumer, AsyncRpcBase):
    async def receive_json(self, content):
        await self._base_receive_json(content)
