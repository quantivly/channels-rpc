"""Example demonstrating RPC method timeout enforcement.

This example shows how to configure timeouts for RPC methods to prevent
DoS attacks from long-running methods.
"""

import os

# Configure Django before importing channels_rpc
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")

import django

django.setup()

import asyncio

from channels_rpc.async_rpc_base import AsyncRpcBase


class TimeoutExampleConsumer(AsyncRpcBase):
    """Example consumer with various timeout configurations."""

    def __init__(self, scope=None):
        self.scope = scope or {"type": "websocket"}
        self.sent_messages = []

    async def send_json(self, data):  # type: ignore[override]
        """Mock send_json to capture sent messages."""
        self.sent_messages.append(data)
        print(f"Sent: {data}")

    async def send(self, data):  # type: ignore[override]
        """Mock send for text messages."""
        self.sent_messages.append(data)

    def encode_json(self, data):
        """Mock JSON encoding."""
        import json

        return json.dumps(data)


# Method with default timeout (300 seconds)
@TimeoutExampleConsumer.rpc_method()
async def default_timeout_method(value: int) -> dict:
    """Method using default 300-second timeout."""
    await asyncio.sleep(0.1)  # Fast operation
    return {"result": value * 2, "timeout": "default (300s)"}


# Method with custom timeout (10 seconds)
@TimeoutExampleConsumer.rpc_method(timeout=10.0)
async def custom_timeout_method(value: int) -> dict:
    """Method with custom 10-second timeout."""
    await asyncio.sleep(0.1)  # Fast operation
    return {"result": value * 3, "timeout": "10s"}


# Method with short timeout that will be exceeded
@TimeoutExampleConsumer.rpc_method(timeout=0.1)
async def slow_method(value: int) -> dict:
    """Method that exceeds its timeout."""
    await asyncio.sleep(1.0)  # Too slow!
    return {"result": value * 4}  # Never reached


# Method with timeout disabled (timeout=0)
@TimeoutExampleConsumer.rpc_method(timeout=0)
async def no_timeout_method(value: int) -> dict:
    """Method with timeout enforcement disabled."""
    await asyncio.sleep(0.5)  # Can take as long as needed
    return {"result": value * 5, "timeout": "disabled"}


# Database method with custom timeout
@TimeoutExampleConsumer.database_rpc_method(timeout=5.0, atomic=False)
def database_method_with_timeout(value: int) -> dict:
    """Database method with 5-second timeout."""
    import time

    time.sleep(0.1)  # Simulate database query
    return {"result": value * 6, "timeout": "5s", "method": "database"}


async def main():
    """Run example demonstrating timeout enforcement."""
    consumer = TimeoutExampleConsumer()

    print("=" * 60)
    print("RPC Method Timeout Enforcement Example")
    print("=" * 60)

    # Test 1: Method with default timeout
    print("\n1. Testing method with default timeout (300s)...")
    request1 = {
        "jsonrpc": "2.0",
        "method": "default_timeout_method",
        "params": {"value": 10},
        "id": 1,
    }
    try:
        result1 = await consumer._process_call(request1)
        print(f"   Success: {result1['result']}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 2: Method with custom timeout
    print("\n2. Testing method with custom 10s timeout...")
    request2 = {
        "jsonrpc": "2.0",
        "method": "custom_timeout_method",
        "params": {"value": 10},
        "id": 2,
    }
    try:
        result2 = await consumer._process_call(request2)
        print(f"   Success: {result2['result']}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 3: Method that exceeds timeout
    print("\n3. Testing slow method (will timeout after 0.1s)...")
    request3 = {
        "jsonrpc": "2.0",
        "method": "slow_method",
        "params": {"value": 10},
        "id": 3,
    }
    try:
        result3 = await consumer._process_call(request3)
        print(f"   Success: {result3}")
    except Exception as e:
        print(f"   Expected timeout error: {type(e).__name__}")
        error_dict = e.as_dict()
        print(f"   Error message: {error_dict['error']['message']}")

    # Test 4: Method with timeout disabled
    print("\n4. Testing method with timeout disabled...")
    request4 = {
        "jsonrpc": "2.0",
        "method": "no_timeout_method",
        "params": {"value": 10},
        "id": 4,
    }
    try:
        result4 = await consumer._process_call(request4)
        print(f"   Success: {result4['result']}")
    except Exception as e:
        print(f"   Error: {e}")

    # Test 5: Database method with timeout
    print("\n5. Testing database method with 5s timeout...")
    request5 = {
        "jsonrpc": "2.0",
        "method": "database_method_with_timeout",
        "params": {"value": 10},
        "id": 5,
    }
    try:
        result5 = await consumer._process_call(request5)
        print(f"   Success: {result5['result']}")
    except Exception as e:
        print(f"   Error: {e}")

    print("\n" + "=" * 60)
    print("Example completed!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
