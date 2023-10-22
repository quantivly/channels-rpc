# import the logging library
import logging

from django.core.serializers.json import DjangoJSONEncoder

from example.django_example.consumer_test import JsonRpcConsumerTest

# Get an instance of a logger
logger = logging.getLogger(__name__)


class MyJsonRpcWebsocketConsumerTest(JsonRpcConsumerTest):
    def connection_groups(self, **_):
        """
        Called to return the list of groups to automatically add/remove
        this connection to/from.
        """
        return ["test"]

    def connect(self):
        """
        Perform things on connection start
        """
        logger.info("connect")
        self.accept()

        # reject
        # self.close()

    def disconnect(self, _):
        """
        Perform things on connection close
        """
        logger.info("disconnect")

        # Do stuff if needed

    def process(self, data, original_msg):
        """
        Made to test thread-safe
        :param data:
        :param original_msg:
        :return:
        """

        return self.__process(data, original_msg)


@MyJsonRpcWebsocketConsumerTest.rpc_method()
def ping(fake_an_error, **_):
    if fake_an_error:
        # Will return an error to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}}
        #  <-- {"id": 1, "jsonrpc": "2.0", "error": {"message": "fake_error", "code": -32000, "data": ["fake_error"]}} # noqa: E501
        raise Exception(False)
    else:
        # Will return a result to the client
        #  --> {"id":1, "jsonrpc":"2.0","method":"mymodule.rpc.ping","params":{}}
        #  <-- {"id": 1, "jsonrpc": "2.0", "result": "pong"}
        return "pong"


class DjangoJsonRpcWebsocketConsumerTest(JsonRpcConsumerTest):
    def encode_json(self, data):
        return DjangoJSONEncoder().encode(data)
