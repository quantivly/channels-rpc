from channels_rpc import JsonRpcWebsocketConsumer


class JsonRpcConsumerTest(JsonRpcWebsocketConsumer):
    @classmethod
    def clean(cls):
        """
        Clean the class method name for tests
        :return: None
        """
        if id(cls) in cls.available_rpc_methods:
            del cls.available_rpc_methods[id(cls)]
