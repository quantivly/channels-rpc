"""Method registry for RPC consumers."""

from __future__ import annotations

from typing import TYPE_CHECKING
from weakref import WeakKeyDictionary

if TYPE_CHECKING:
    from channels_rpc.rpc_base import RpcMethodWrapper


class MethodRegistry:
    """Registry for RPC methods and notifications.

    Uses WeakKeyDictionary to prevent memory leaks while maintaining
    class-level method registration.

    Attributes
    ----------
    _methods : WeakKeyDictionary
        Mapping of consumer classes to their registered methods.
    _notifications : WeakKeyDictionary
        Mapping of consumer classes to their registered notifications.
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._methods: WeakKeyDictionary = WeakKeyDictionary()
        self._notifications: WeakKeyDictionary = WeakKeyDictionary()

    def register_method(
        self,
        consumer_class: type,
        method_name: str,
        method: RpcMethodWrapper,
    ) -> None:
        """Register an RPC method for a consumer class.

        Parameters
        ----------
        consumer_class : type
            The consumer class to register the method for.
        method_name : str
            Name of the method.
        method : RpcMethodWrapper
            The wrapped method to register.
        """
        if consumer_class not in self._methods:
            self._methods[consumer_class] = {}
        self._methods[consumer_class][method_name] = method

    def register_notification(
        self,
        consumer_class: type,
        method_name: str,
        method: RpcMethodWrapper,
    ) -> None:
        """Register an RPC notification for a consumer class.

        Parameters
        ----------
        consumer_class : type
            The consumer class to register the notification for.
        method_name : str
            Name of the notification.
        method : RpcMethodWrapper
            The wrapped method to register.
        """
        if consumer_class not in self._notifications:
            self._notifications[consumer_class] = {}
        self._notifications[consumer_class][method_name] = method

    def get_methods(self, consumer_class: type) -> dict[str, RpcMethodWrapper]:
        """Get all RPC methods for a consumer class.

        Parameters
        ----------
        consumer_class : type
            The consumer class.

        Returns
        -------
        dict[str, RpcMethodWrapper]
            Dictionary mapping method names to methods.
        """
        return self._methods.get(consumer_class, {})

    def get_notifications(self, consumer_class: type) -> dict[str, RpcMethodWrapper]:
        """Get all RPC notifications for a consumer class.

        Parameters
        ----------
        consumer_class : type
            The consumer class.

        Returns
        -------
        dict[str, RpcMethodWrapper]
            Dictionary mapping notification names to methods.
        """
        return self._notifications.get(consumer_class, {})

    def get_method(
        self, consumer_class: type, method_name: str
    ) -> RpcMethodWrapper | None:
        """Get a specific RPC method.

        Parameters
        ----------
        consumer_class : type
            The consumer class.
        method_name : str
            Name of the method.

        Returns
        -------
        RpcMethodWrapper | None
            The method if found, None otherwise.
        """
        methods: dict[str, RpcMethodWrapper] = self._methods.get(consumer_class, {})
        return methods.get(method_name)

    def has_method(self, consumer_class: type, method_name: str) -> bool:
        """Check if a method is registered.

        Parameters
        ----------
        consumer_class : type
            The consumer class.
        method_name : str
            Name of the method.

        Returns
        -------
        bool
            True if method is registered.
        """
        return method_name in self._methods.get(consumer_class, {})

    def list_method_names(self, consumer_class: type) -> list[str]:
        """List all registered method names for a class.

        Parameters
        ----------
        consumer_class : type
            The consumer class.

        Returns
        -------
        list[str]
            List of method names.
        """
        return list(self._methods.get(consumer_class, {}).keys())


# Global registry instance
_registry = MethodRegistry()


def get_registry() -> MethodRegistry:
    """Get the global method registry.

    Returns
    -------
    MethodRegistry
        The global registry instance.
    """
    return _registry
