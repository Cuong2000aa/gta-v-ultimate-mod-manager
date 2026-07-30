"""A minimal, explicit dependency-injection container.

The container maps a *type key* (usually a Protocol or ABC) to either a
singleton instance or a factory. Nothing is auto-wired by reflection: the
composition root in :mod:`gta_mod_manager.app` states every binding, which
keeps the object graph readable and testable.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any, TypeVar, cast

from gta_mod_manager.core.exceptions import ConfigurationError

T = TypeVar("T")


class Container:
    """Registry of application services keyed by type."""

    def __init__(self) -> None:
        self._singletons: dict[type[Any], Any] = {}
        self._factories: dict[type[Any], Callable[[Container], Any]] = {}
        self._lock = threading.RLock()

    def register_instance(self, key: type[T], instance: T) -> None:
        """Bind ``key`` to an already constructed ``instance``."""
        with self._lock:
            self._singletons[key] = instance

    def register_factory(
        self, key: type[T], factory: Callable[[Container], T], *, singleton: bool = True
    ) -> None:
        """Bind ``key`` to a factory.

        Args:
            key: The type used to resolve the dependency.
            factory: Callable receiving the container and returning the value.
            singleton: When ``True`` the value is created once and cached.
        """
        with self._lock:
            if singleton:
                self._factories[key] = _SingletonFactory(factory)
            else:
                self._factories[key] = factory

    def resolve(self, key: type[T]) -> T:
        """Return the instance bound to ``key``.

        Raises:
            ConfigurationError: When no binding exists.
        """
        with self._lock:
            if key in self._singletons:
                return cast(T, self._singletons[key])
            factory = self._factories.get(key)
        if factory is None:
            raise ConfigurationError("No binding registered", dependency=key.__name__)
        return cast(T, factory(self))

    def try_resolve(self, key: type[T]) -> T | None:
        """Return the instance bound to ``key`` or ``None`` when unbound."""
        try:
            return self.resolve(key)
        except ConfigurationError:
            return None

    def has(self, key: type[Any]) -> bool:
        """Return whether ``key`` has a binding."""
        with self._lock:
            return key in self._singletons or key in self._factories


class _SingletonFactory:
    """Wraps a factory so the produced value is created exactly once."""

    def __init__(self, factory: Callable[[Container], Any]) -> None:
        self._factory = factory
        self._value: Any = None
        self._created = False
        self._lock = threading.RLock()

    def __call__(self, container: Container) -> Any:
        """Create the value on first call and return the cached one after."""
        with self._lock:
            if not self._created:
                self._value = self._factory(container)
                self._created = True
            return self._value
