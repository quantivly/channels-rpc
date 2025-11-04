from channels.generic.websocket import AsyncJsonWebsocketConsumer

from channels_rpc.async_rpc_base import AsyncRpcBase


class AsyncJsonRpcWebsocketConsumer(AsyncJsonWebsocketConsumer, AsyncRpcBase):
    """Async WebSocket consumer for JSON-RPC 2.0 communication.
    This consumer provides asynchronous support for handling JSON-RPC 2.0 requests
    over WebSocket connections. Use this class when your RPC methods are async
    functions or when you need to leverage Django Channels' async capabilities
    for better concurrency.

    This class combines Django Channels' AsyncJsonWebsocketConsumer with the
    AsyncRpcBase mixin to provide full async RPC functionality.

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

    async def receive_json(self, content):
        await self._base_receive_json(content)
