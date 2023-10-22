from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from django.urls import re_path

from example.django_example.consumer import (
    DjangoJsonRpcWebsocketConsumerTest,
    MyJsonRpcWebsocketConsumerTest,
)

websocket_urlpatterns = [
    re_path(r"^django/$", DjangoJsonRpcWebsocketConsumerTest),
    re_path(r"^ws/", MyJsonRpcWebsocketConsumerTest),
]

application = ProtocolTypeRouter(
    {
        "websocket": AuthMiddlewareStack(URLRouter(websocket_urlpatterns)),
    }
)
