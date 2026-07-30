"""Tests for the dependency injection container."""

from __future__ import annotations

import pytest

from gta_mod_manager.core.container import Container
from gta_mod_manager.core.exceptions import ConfigurationError


class Service:
    """Stand-in dependency."""

    def __init__(self, label: str = "default") -> None:
        self.label = label


def test_registered_instances_are_returned_as_is() -> None:
    container = Container()
    service = Service("explicit")
    container.register_instance(Service, service)

    assert container.resolve(Service) is service


def test_factories_are_only_invoked_once() -> None:
    container = Container()
    calls: list[int] = []

    def factory(_container: Container) -> Service:
        calls.append(1)
        return Service("lazy")

    container.register_factory(Service, factory)

    first = container.resolve(Service)
    second = container.resolve(Service)

    assert first is second
    assert calls == [1]


def test_resolving_an_unknown_type_raises() -> None:
    with pytest.raises(ConfigurationError):
        Container().resolve(Service)


def test_try_resolve_returns_none_for_unknown_types() -> None:
    assert Container().try_resolve(Service) is None
