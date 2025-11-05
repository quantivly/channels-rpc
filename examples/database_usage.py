"""Example usage of @database_rpc_method decorator.

This example demonstrates how to use the @database_rpc_method decorator
to safely access Django ORM from async RPC methods.
"""

from channels_rpc import AsyncJsonRpcWebsocketConsumer


class MyConsumer(AsyncJsonRpcWebsocketConsumer):
    """Example consumer with database-accessing RPC methods."""

    pass


# Example 1: Simple database method
@MyConsumer.database_rpc_method()
def get_user(user_id: int):
    """Get user information from database.

    This is a SYNC function that can safely use Django ORM.
    It will be automatically wrapped with database_sync_to_async.
    """
    # This would be actual Django ORM code:
    # from myapp.models import User
    # user = User.objects.get(id=user_id)
    # return {
    #     "id": user.id,
    #     "username": user.username,
    #     "email": user.email,
    # }

    # For this example, we'll return mock data
    return {
        "id": user_id,
        "username": f"user_{user_id}",
        "email": f"user_{user_id}@example.com",
    }


# Example 2: Method with custom name
@MyConsumer.database_rpc_method("users.list")
def list_users(limit: int = 10):
    """List users from database.

    Custom method name allows namespacing (e.g., "users.list").
    """
    # This would be actual Django ORM code:
    # from myapp.models import User
    # users = User.objects.all()[:limit]
    # return [{"id": u.id, "username": u.username} for u in users]

    # For this example, we'll return mock data
    return [{"id": i, "username": f"user_{i}"} for i in range(1, limit + 1)]


# Example 3: Method with consumer context access
@MyConsumer.database_rpc_method()
def get_current_user(ctx):
    """Get current user from consumer context.

    Uses RpcContext parameter to access the consumer instance and scope.
    This is the modern way to access consumer context (replaces **kwargs).
    """
    from channels_rpc import RpcContext

    # Type hint for IDE support (optional, can also be in function signature)
    # ctx is typed through the function signature or can be annotated inline
    # Access consumer scope for session data, authenticated user, etc.
    session = ctx.scope.get("session", {})
    user_id = session.get("user_id")

    # Or access the authenticated user directly
    user = ctx.scope.get("user")

    # This would be actual Django ORM code:
    # from myapp.models import User
    # if user and user.is_authenticated:
    #     db_user = User.objects.get(id=user.id)
    #     return {"id": db_user.id, "username": db_user.username}

    # For this example, we'll return mock data
    return (
        {"id": user_id, "username": f"user_{user_id}"}
        if user_id
        else {"error": "Not authenticated"}
    )


# Example 4: Complex query method
@MyConsumer.database_rpc_method("users.search")
def search_users(query: str, limit: int = 10):
    """Search users by query string.

    This demonstrates a more complex database operation.
    """
    # This would be actual Django ORM code:
    # from django.db.models import Q
    # from myapp.models import User
    #
    # users = User.objects.filter(
    #     Q(username__icontains=query) | Q(email__icontains=query)
    # )[:limit]
    #
    # return [
    #     {
    #         "id": u.id,
    #         "username": u.username,
    #         "email": u.email,
    #         "created_at": u.created_at.isoformat(),
    #     }
    #     for u in users
    # ]

    # For this example, we'll return mock data
    return [
        {
            "id": i,
            "username": f"user_{query}_{i}",
            "email": f"user_{query}_{i}@example.com",
        }
        for i in range(1, min(limit, 5) + 1)
    ]


# Example JSON-RPC calls:
#
# 1. Get user by ID:
# {
#     "jsonrpc": "2.0",
#     "method": "get_user",
#     "params": {"user_id": 42},
#     "id": 1
# }
#
# 2. List users:
# {
#     "jsonrpc": "2.0",
#     "method": "users.list",
#     "params": {"limit": 20},
#     "id": 2
# }
#
# 3. Get current user:
# {
#     "jsonrpc": "2.0",
#     "method": "get_current_user",
#     "params": {},
#     "id": 3
# }
#
# 4. Search users:
# {
#     "jsonrpc": "2.0",
#     "method": "users.search",
#     "params": {"query": "john", "limit": 10},
#     "id": 4
# }
