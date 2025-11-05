"""Django signals for RPC lifecycle events.

This module provides signals that are emitted at various points in the RPC
request lifecycle. These signals enable monitoring, logging, metrics collection,
and integration with APM tools without modifying the core RPC logic.

Signals
-------
rpc_method_started
    Sent when an RPC method starts executing.
rpc_method_completed
    Sent when an RPC method completes successfully.
rpc_method_failed
    Sent when an RPC method raises an error.
rpc_client_connected
    Sent when a WebSocket client connects.
rpc_client_disconnected
    Sent when a WebSocket client disconnects.

Examples
--------
Monitor RPC method execution times::

    from channels_rpc.signals import rpc_method_started, rpc_method_completed
    import time

    execution_times = {}

    def on_method_started(sender, consumer, method_name, rpc_id, **kwargs):
        execution_times[rpc_id] = time.time()

    def on_method_completed(
        sender, consumer, method_name, result, rpc_id, duration, **kwargs
    ):
        if rpc_id in execution_times:
            actual_duration = time.time() - execution_times[rpc_id]
            print(f"{method_name} took {actual_duration:.3f}s")
            del execution_times[rpc_id]

    rpc_method_started.connect(on_method_started)
    rpc_method_completed.connect(on_method_completed)

Collect metrics for monitoring::

    from channels_rpc.signals import rpc_method_completed, rpc_method_failed

    metrics = {"success": 0, "errors": 0}

    def on_success(sender, **kwargs):
        metrics["success"] += 1

    def on_failure(sender, **kwargs):
        metrics["errors"] += 1

    rpc_method_completed.connect(on_success)
    rpc_method_failed.connect(on_failure)

Integrate with APM tools::

    from channels_rpc.signals import rpc_method_started, rpc_method_completed
    import newrelic.agent

    def on_method_started(sender, method_name, **kwargs):
        newrelic.agent.set_transaction_name(f"RPC/{method_name}")

    def on_method_completed(sender, method_name, duration, **kwargs):
        newrelic.agent.record_custom_metric(
            f"Custom/RPC/{method_name}/Duration",
            duration
        )

    rpc_method_started.connect(on_method_started)
    rpc_method_completed.connect(on_method_completed)

Notes
-----
Signals are sent synchronously in the same thread/task as the RPC call.
Keep signal handlers lightweight to avoid impacting RPC performance.

For async consumers, signal handlers should be synchronous functions.
Django signals do not support async receivers.

.. versionadded:: 1.0.0
   Added RPC lifecycle signals for monitoring and instrumentation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Union

if TYPE_CHECKING:
    from django.dispatch import Signal

try:
    from django.dispatch import Signal as DjangoSignal

    _DJANGO_AVAILABLE = True

    # RPC method lifecycle signals
    rpc_method_started: Signal | DummySignal = DjangoSignal()
    """Sent when an RPC method starts executing.

    Arguments:
        sender: The consumer class
        consumer: The consumer instance
        method_name (str): Name of the RPC method
        params (dict | list): Method parameters
        rpc_id (str | int | None): Request ID
    """

    rpc_method_completed: Signal | DummySignal = DjangoSignal()
    """Sent when an RPC method completes successfully.

    Arguments:
        sender: The consumer class
        consumer: The consumer instance
        method_name (str): Name of the RPC method
        result: The method's return value
        rpc_id (str | int | None): Request ID
        duration (float): Execution time in seconds
    """

    rpc_method_failed: Signal | DummySignal = DjangoSignal()
    """Sent when an RPC method raises an error.

    Arguments:
        sender: The consumer class
        consumer: The consumer instance
        method_name (str): Name of the RPC method
        error (Exception): The exception that was raised
        rpc_id (str | int | None): Request ID
        duration (float): Time before failure in seconds
    """

    # WebSocket connection lifecycle signals
    rpc_client_connected: Signal | DummySignal = DjangoSignal()
    """Sent when a WebSocket client connects.

    Arguments:
        sender: The consumer class
        consumer: The consumer instance
        scope (dict): ASGI connection scope
    """

    rpc_client_disconnected: Signal | DummySignal = DjangoSignal()
    """Sent when a WebSocket client disconnects.

    Arguments:
        sender: The consumer class
        consumer: The consumer instance
        scope (dict): ASGI connection scope
        duration (float): Connection duration in seconds
        close_code (int | None): WebSocket close code
    """

except ImportError:
    # Django not available - create dummy signals that do nothing
    _DJANGO_AVAILABLE = False

    class DummySignal:
        """Placeholder signal when Django is not installed."""

        def connect(
            self,
            receiver: Any = None,
            sender: Any = None,
            weak: bool = True,  # noqa: FBT001, FBT002
            dispatch_uid: Any = None,
        ) -> None:
            """No-op connect method."""
            pass

        def disconnect(
            self, receiver: Any = None, sender: Any = None, dispatch_uid: Any = None
        ) -> None:
            """No-op disconnect method."""
            pass

        def send(self, sender: Any, **kwargs: Any) -> list:  # noqa: ARG002
            """No-op send method."""
            return []

        def send_robust(self, sender: Any, **kwargs: Any) -> list:  # noqa: ARG002
            """No-op send_robust method."""
            return []

    rpc_method_started = DummySignal()
    rpc_method_completed = DummySignal()
    rpc_method_failed = DummySignal()
    rpc_client_connected = DummySignal()
    rpc_client_disconnected = DummySignal()


__all__ = [
    "rpc_client_connected",
    "rpc_client_disconnected",
    "rpc_method_completed",
    "rpc_method_failed",
    "rpc_method_started",
]
