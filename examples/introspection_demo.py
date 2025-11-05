"""Demonstration of the enhanced method introspection API.

This script shows how to use the new introspection methods:
- get_method_info() - Get detailed metadata about a specific method
- describe_api() - Get a comprehensive API description

Usage:
    python examples/introspection_demo.py
"""

from __future__ import annotations

import json
import os
from typing import Any

# Configure Django before importing channels_rpc
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

django.setup()

from channels_rpc import AsyncJsonRpcWebsocketConsumer
from channels_rpc.context import RpcContext


class DemoConsumer(AsyncJsonRpcWebsocketConsumer):
    """Example consumer with various RPC methods for introspection demo."""

    pass


@DemoConsumer.rpc_method()
async def get_user(self, user_id: int) -> dict[str, Any]:
    """Get user information by ID.

    Parameters
    ----------
    user_id : int
        The unique identifier of the user.

    Returns
    -------
    dict[str, Any]
        User information including id, name, and email.

    Examples
    --------
    >>> await consumer.get_user(user_id=123)
    {'id': 123, 'name': 'John Doe', 'email': 'john@example.com'}
    """
    return {
        "id": user_id,
        "name": "John Doe",
        "email": "john@example.com",
    }


@DemoConsumer.rpc_method()
async def create_resource(
    self,
    ctx: RpcContext,
    name: str,
    description: str = "",
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new resource with context access.

    This method demonstrates RpcContext usage for accessing
    consumer state and connection information.

    Parameters
    ----------
    ctx : RpcContext
        RPC execution context with consumer and request metadata.
    name : str
        Resource name.
    description : str, optional
        Resource description, by default empty string.
    tags : list[str] | None, optional
        Resource tags, by default None.

    Returns
    -------
    dict[str, Any]
        Created resource with generated ID.
    """
    return {
        "id": 456,
        "name": name,
        "description": description,
        "tags": tags or [],
        "created_by": ctx.consumer.__class__.__name__,
    }


@DemoConsumer.rpc_method(websocket=True)
async def stream_data(self, channel: str, limit: int = 100) -> dict[str, Any]:
    """Stream data from a channel (WebSocket only).

    Parameters
    ----------
    channel : str
        Channel name to stream from.
    limit : int, optional
        Maximum number of items to stream, by default 100.

    Returns
    -------
    dict[str, Any]
        Stream metadata and item count.
    """
    return {
        "channel": channel,
        "items_sent": min(limit, 50),
        "has_more": limit > 50,
    }


@DemoConsumer.rpc_notification()
async def log_event(self, event_type: str, data: dict[str, Any]) -> None:
    """Log an event (notification handler).

    Parameters
    ----------
    event_type : str
        Type of event being logged.
    data : dict[str, Any]
        Event payload data.

    Notes
    -----
    This is a notification handler and does not return a response.
    """
    print(f"Event logged: {event_type} - {data}")


def main() -> None:
    """Demonstrate the introspection API."""
    print("=" * 80)
    print("Enhanced Method Introspection API Demo")
    print("=" * 80)
    print()

    # Get list of all methods
    print("1. Get list of all RPC methods:")
    print("-" * 80)
    methods = DemoConsumer.get_rpc_methods()
    print(f"Found {len(methods)} methods: {', '.join(methods)}")
    print()

    # Get list of all notifications
    print("2. Get list of all notification handlers:")
    print("-" * 80)
    notifications = DemoConsumer.get_rpc_notifications()
    print(f"Found {len(notifications)} notifications: {', '.join(notifications)}")
    print()

    # Get detailed info about a specific method
    print("3. Get detailed info about 'create_resource' method:")
    print("-" * 80)
    info = DemoConsumer.get_method_info("create_resource")
    print(f"Name: {info.name}")
    print(f"Accepts Context: {info.accepts_context}")
    print(f"Is Notification: {info.is_notification}")
    print(f"Transport Options: {info.transport_options}")
    print(f"Signature: {info.signature}")
    docstring_preview = info.docstring[:100] if info.docstring else "None"
    print(f"Docstring (first 100 chars): {docstring_preview}...")
    print()

    # Get info about a notification
    print("4. Get detailed info about 'log_event' notification:")
    print("-" * 80)
    notif_info = DemoConsumer.get_method_info("log_event")
    print(f"Name: {notif_info.name}")
    print(f"Is Notification: {notif_info.is_notification}")
    print(f"Signature: {notif_info.signature}")
    print()

    # Get comprehensive API description
    print("5. Get comprehensive API description (JSON):")
    print("-" * 80)
    api_desc = DemoConsumer.describe_api()
    print(json.dumps(api_desc, indent=2))
    print()

    # Show how this could be used for API documentation
    print("6. Example: Generate simple API documentation:")
    print("-" * 80)
    print(f"API for {api_desc['consumer']}")
    print(f"JSON-RPC Version: {api_desc['jsonrpc']}")
    print()
    print("Methods:")
    for method in api_desc["methods"]:
        ctx_marker = " [Context]" if method["accepts_context"] else ""
        print(f"  - {method['name']}{ctx_marker}")
        print(f"    Signature: {method['signature']}")
        if method["doc"]:
            first_line = method["doc"].split("\n")[0]
            print(f"    Description: {first_line}")
        print(f"    Transports: {', '.join(method['transports'])}")
        print()

    print("Notifications:")
    for notif in api_desc["notifications"]:
        print(f"  - {notif['name']}")
        print(f"    Signature: {notif['signature']}")
        if notif["doc"]:
            first_line = notif["doc"].split("\n")[0]
            print(f"    Description: {first_line}")
        print()

    print("=" * 80)
    print("Demo complete!")
    print("=" * 80)


if __name__ == "__main__":
    main()
