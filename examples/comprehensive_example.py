# ruff: noqa
"""Comprehensive example showcasing channels-rpc 1.0.0 features.

This example demonstrates all major features added or improved in version 1.0.0:
- RpcContext for type-safe parameter access
- Custom JSON encoder for datetime/Decimal serialization
- Middleware for cross-cutting concerns
- Django signals for monitoring
- Permission-based access control
- Enhanced error codes
"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal

from channels_rpc import AsyncJsonRpcWebsocketConsumer, RpcContext
from channels_rpc.decorators import permission_required
from channels_rpc.exceptions import JsonRpcError, JsonRpcErrorCode


# ------------------------------------------------------------------------------
# Custom JSON Encoder
# ------------------------------------------------------------------------------
class CustomEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime and Decimal serialization."""

    def default(self, obj):
        """Encode datetime and Decimal objects."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Decimal):
            return float(obj)
        return super().default(obj)


# ------------------------------------------------------------------------------
# Middleware Example
# ------------------------------------------------------------------------------
class LoggingMiddleware:
    """Middleware that logs all RPC calls."""

    def process_request(self, data, consumer):
        """Log incoming requests."""
        print(f"[RPC] Incoming: {data.get('method')}")
        return data

    def process_response(self, response, consumer):
        """Log outgoing responses."""
        print(f"[RPC] Outgoing: {response.get('id')}")
        return response


class AuthMiddleware:
    """Middleware that adds auth metadata to responses."""

    def process_request(self, data, consumer):
        """Validate authentication."""
        user = consumer.scope.get("user")
        if not user or not user.is_authenticated:
            # You could raise JsonRpcError here to reject unauthenticated requests
            pass
        return data

    def process_response(self, response, consumer):
        """Add auth info to response."""
        user = consumer.scope.get("user")
        if user and user.is_authenticated:
            response["_auth"] = {"user_id": user.id, "username": user.username}
        return response


# ------------------------------------------------------------------------------
# Consumer with All Features
# ------------------------------------------------------------------------------
class AdvancedConsumer(AsyncJsonRpcWebsocketConsumer):
    """Consumer showcasing all 1.0.0 features.

    Features demonstrated:
    - Custom JSON encoder for datetime/Decimal
    - Middleware pipeline
    - RpcContext usage
    - Permission-based access control
    - Enhanced error codes
    """

    # Custom JSON encoder for serializing datetime, Decimal, etc.
    json_encoder_class = CustomEncoder

    # Middleware pipeline (applied in order)
    middleware = [
        LoggingMiddleware(),
        AuthMiddleware(),
    ]


# ------------------------------------------------------------------------------
# Example 1: Using RpcContext
# ------------------------------------------------------------------------------
@AdvancedConsumer.rpc_method()
async def get_user_info(ctx: RpcContext, user_id: int) -> dict:
    """Get user information using RpcContext.

    The RpcContext parameter provides type-safe access to:
    - ctx.consumer: The consumer instance
    - ctx.scope: ASGI connection scope
    - ctx.method_name: The RPC method name
    - ctx.rpc_id: The request ID
    - ctx.is_notification: Whether this is a notification
    """
    # Access authenticated user from scope
    user = ctx.scope.get("user")

    # Access session data
    session = ctx.scope.get("session", {})

    return {
        "requested_user_id": user_id,
        "current_user": user.username if user and user.is_authenticated else None,
        "session_key": session.get("session_key"),
        "method": ctx.method_name,
    }


# ------------------------------------------------------------------------------
# Example 2: Custom JSON Encoder
# ------------------------------------------------------------------------------
@AdvancedConsumer.rpc_method()
async def get_transaction_data() -> dict:
    """Return data with datetime and Decimal (serialized by custom encoder)."""
    return {
        "timestamp": datetime.now(),  # Will be serialized to ISO format
        "amount": Decimal("123.45"),  # Will be serialized to float
        "description": "Payment received",
    }


# ------------------------------------------------------------------------------
# Example 3: Permission-Based Access Control
# ------------------------------------------------------------------------------
@AdvancedConsumer.rpc_method()
@permission_required("myapp.can_delete_users")
async def delete_user(ctx: RpcContext, user_id: int) -> dict:
    """Delete a user (requires permission).

    Only users with 'myapp.can_delete_users' permission can call this.
    Returns METHOD_NOT_FOUND error (not permission denied) to prevent
    information disclosure.
    """
    # This would be actual code:
    # from myapp.models import User
    # User.objects.get(id=user_id).delete()

    return {"deleted": True, "user_id": user_id}


@AdvancedConsumer.rpc_method()
@permission_required("myapp.view_reports", "myapp.export_data")
async def export_report(ctx: RpcContext, report_id: int) -> dict:
    """Export report (requires multiple permissions).

    User must have BOTH permissions to call this method.
    """
    return {"report_id": report_id, "exported": True}


# ------------------------------------------------------------------------------
# Example 4: Error Handling
# ------------------------------------------------------------------------------
@AdvancedConsumer.rpc_method()
async def update_user(ctx: RpcContext, user_id: int, data: dict) -> dict:
    """Update user with proper error handling.

    Demonstrates using standard error codes for error handling.
    """
    # Input validation
    if not data.get("email"):
        raise JsonRpcError(
            ctx.rpc_id,
            JsonRpcErrorCode.INVALID_PARAMS,
            data={"field": "email", "error": "required"},
        )

    # Business logic error
    # In real code, check if user exists
    user_exists = user_id > 0
    if not user_exists:
        raise JsonRpcError(
            ctx.rpc_id,
            JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
            data={"resource": "user", "id": user_id},
        )

    # Conflict check
    # Example: User already has this email
    if data.get("email") == "taken@example.com":
        raise JsonRpcError(
            ctx.rpc_id,
            JsonRpcErrorCode.GENERIC_APPLICATION_ERROR,
            data={"field": "email", "error": "already exists"},
        )

    return {"updated": True, "user_id": user_id}


@AdvancedConsumer.rpc_method()
async def fetch_external_data(url: str) -> dict:
    """Fetch data from external service.

    Demonstrates error handling for external failures.
    """
    try:
        # Simulated external API call
        # import httpx
        # async with httpx.AsyncClient() as client:
        #     response = await client.get(url)
        #     return {"data": response.json()}

        # Simulate external service error
        if "fail" in url:
            raise JsonRpcError(
                None,
                JsonRpcErrorCode.INTERNAL_ERROR,
                data={"service": "external-api"},
            )

        return {"data": "success"}

    except Exception as e:
        # External failure
        raise JsonRpcError(
            None,
            JsonRpcErrorCode.INTERNAL_ERROR,
            data={"error": str(e)},
        )


# ------------------------------------------------------------------------------
# Example 5: Notifications (one-way messages)
# ------------------------------------------------------------------------------
@AdvancedConsumer.rpc_notification()
async def client_heartbeat(ctx: RpcContext, timestamp: float) -> None:
    """Handle client heartbeat notification.

    Notifications don't send responses. They should return None.
    """
    print(f"Heartbeat from client at {timestamp}")
    # Could update last_seen timestamp in database
    # Could track connection health metrics


# ------------------------------------------------------------------------------
# Django Signals Integration
# ------------------------------------------------------------------------------
# In your Django app, connect to signals for monitoring:
#
# from channels_rpc.signals import (
#     rpc_method_started,
#     rpc_method_completed,
#     rpc_method_failed,
#     rpc_client_connected,
#     rpc_client_disconnected,
# )
#
# def track_rpc_metrics(sender, method_name, duration, **kwargs):
#     # Send to metrics service (DataDog, Prometheus, etc.)
#     print(f"Method {method_name} took {duration:.3f}s")
#
# def alert_on_errors(sender, method_name, error, **kwargs):
#     # Send to alerting service (PagerDuty, Slack, etc.)
#     print(f"ERROR in {method_name}: {error}")
#
# rpc_method_completed.connect(track_rpc_metrics)
# rpc_method_failed.connect(alert_on_errors)


# ------------------------------------------------------------------------------
# Example JSON-RPC Requests
# ------------------------------------------------------------------------------

# 1. Get user info (with RpcContext):
# {
#     "jsonrpc": "2.0",
#     "method": "get_user_info",
#     "params": {"user_id": 42},
#     "id": 1
# }

# 2. Get transaction data (datetime/Decimal serialization):
# {
#     "jsonrpc": "2.0",
#     "method": "get_transaction_data",
#     "params": {},
#     "id": 2
# }

# 3. Delete user (requires permission):
# {
#     "jsonrpc": "2.0",
#     "method": "delete_user",
#     "params": {"user_id": 42},
#     "id": 3
# }
# Response if unauthorized:
# {
#     "jsonrpc": "2.0",
#     "error": {"code": -32601, "message": "Method Not Found: 'delete_user'"},
#     "id": 3
# }

# 4. Update user (enhanced error codes):
# {
#     "jsonrpc": "2.0",
#     "method": "update_user",
#     "params": {"user_id": 42, "data": {"email": "new@example.com"}},
#     "id": 4
# }
# Response if validation fails:
# {
#     "jsonrpc": "2.0",
#     "error": {
#         "code": -32002,
#         "message": "Validation Error",
#         "data": {"field": "email", "error": "required"}
#     },
#     "id": 4
# }

# 5. Heartbeat notification (no response):
# {
#     "jsonrpc": "2.0",
#     "method": "client_heartbeat",
#     "params": {"timestamp": 1699123456.789}
# }
