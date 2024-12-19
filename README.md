# channels-rpc

`channels-rpc`` is aimed to enable [JSON-RPC](http://json-rpc.org/) functionnality
on top of the excellent django channels project and especially their Websockets
functionality. It is aimed to be:

- Fully integrated with Channels
- Fully implement JSON-RPC 1 and 2 protocol
- Support both WebSocket and HTTP transports
- Easy integration

## Installation

```sh
$ pip install git+ssh://git@github.com/quantivly/channels-rpc.git
```

## Use

It is intended to be used as a WebSocket consumer:

```python
from channels_rpc import JsonRpcWebsocketConsumer

class MyJsonRpcConsumer(JsonRpcConsumer):

    def connect(self, message, **kwargs):
        """Perform things on WebSocket connection start"""
        self.accept()
        print("connect")
        # Do stuff if needed

    def disconnect(self, message, **kwargs):
        """Perform things on WebSocket connection close"""
        print("disconnect")
        # Do stuff if needed

```

JsonRpcWebsocketConsumer derives from `channels`
[JsonWebsocketConsumer](https://channels.readthedocs.io/en/latest/topics/consumers.html#websocketconsumer).
Then, the last step is to create the RPC methos hooks using the `rpc_method`
decorator:

```python
@MyJsonRpcConsumer.rpc_method()
def ping():
    return "pong"
```

Or, with a custom name:

```python
@MyJsonRpcConsumer.rpc_method("mymodule.rpc.ping")
def ping():
    return "pong"
```

Will now be callable with `"method":"mymodule.rpc.ping"` in the rpc call:

```javascript
{
    "id":1,
    "jsonrpc":"2.0",
    "method":"mymodule.rpc.ping",
    "params":{}
}
```

RPC methods can obviously accept parameters. They also return "results" or "errors":

```python
@MyJsonRpcConsumer.rpc_method("mymodule.rpc.ping")
def ping(fake_an_error):
    if fake_an_error:
        # Will return an error to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}} #  <-- {"id": 1, "jsonrpc": "2.0", "error": {"message": "fake_error", "code": -32000, "data": ["fake_error"]}}  raise Exception("fake_error")
    else:
        # Will return a result to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}} #  <-- {"id": 1, "jsonrpc": "2.0", "result": "pong"}  return "pong"
```

## Async Use

Simply derive your customer from an asynchronous customer like
`AsyncJsonRpcWebsocketConsumer`:

```python
from channels_rpc import AsyncJsonRpcWebsocketConsumer

class MyAsyncJsonRpcConsumer(AsyncJsonRpcWebsocketConsumer):
	pass

@MyAsyncJsonRpcConsumer.rpc_method("mymodule.rpc.ping")
async def ping(fake_an_error):
    return "ping"
```

## [Sessions and other parameters from Consumer object](#consumer)

The original channel message - that can contain sessions (if activated with
[http_user](https://channels.readthedocs.io/en/stable/generics.html#websockets))
and other important info can be easily accessed by retrieving the `**kwargs`
and get a parameter named _consumer_.

```python
MyJsonRpcConsumerTest.rpc_method()
def json_rpc_method(param1, **kwargs):
    consumer = kwargs["consumer"]
    ##do something with consumer
```

Example:

```python
class MyJsonRpcConsumerTest(JsonRpcConsumer):
    # Set to True to automatically port users from HTTP cookies
    # (you don't need channel_session_user, this implies it) # https://channels.readthedocs.io/en/stable/generics.html#websockets  http_user = True

....

@MyJsonRpcConsumerTest.rpc_method()
def ping(**kwargs):
    consumer = kwargs["consumer"]
    consumer.scope["session"]["test"] = True
    return "pong"

```

## Testing

The JsonRpcConsumer class can be tested the same way Channels Consumers are tested.
See [here](http://channels.readthedocs.io/en/stable/testing.html)
