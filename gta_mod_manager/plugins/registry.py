"""Discovery and lookup of game plugins."""

from __future__ import annotations

import importlib
import pkgutil
from types import ModuleType

from gta_mod_manager.core.exceptions import PluginLoadError, PluginNotFoundError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.plugins.contracts import GamePlugin

_LOGGER = get_logger("plugins.registry")

#: Name of the factory function a plugin module must expose.
PLUGIN_FACTORY_NAME = "create_plugin"


class PluginRegistry:
    """Holds the available :class:`GamePlugin` instances."""

    def __init__(self) -> None:
        self._plugins: dict[str, GamePlugin] = {}

    def register(self, plugin: GamePlugin) -> None:
        """Add ``plugin``, replacing any plugin with the same game id."""
        self._plugins[plugin.game_id] = plugin
        _LOGGER.info(
            "Registered plugin %s (%s)", plugin.metadata.display_name, plugin.game_id
        )

    def get(self, game_id: str) -> GamePlugin:
        """Return the plugin for ``game_id``.

        Raises:
            PluginNotFoundError: When no plugin is registered for that game.
        """
        plugin = self._plugins.get(game_id)
        if plugin is None:
            raise PluginNotFoundError("No plugin registered for this game", game_id=game_id)
        return plugin

    def try_get(self, game_id: str) -> GamePlugin | None:
        """Return the plugin for ``game_id``, or ``None`` when absent."""
        return self._plugins.get(game_id)

    def all(self) -> tuple[GamePlugin, ...]:
        """Return every registered plugin."""
        return tuple(self._plugins.values())

    @property
    def game_ids(self) -> tuple[str, ...]:
        """Return the identifiers of every registered plugin."""
        return tuple(self._plugins)

    def __len__(self) -> int:
        """Return how many plugins are registered."""
        return len(self._plugins)


def discover_plugins(package: ModuleType | None = None) -> PluginRegistry:
    """Import every submodule package of ``package`` and register its plugin.

    A plugin package must expose a module-level ``create_plugin()`` factory in
    its ``__init__`` or in a ``plugin`` submodule.

    Args:
        package: Package to scan; defaults to :mod:`gta_mod_manager.plugins`.

    Returns:
        A registry containing every plugin that could be loaded.
    """
    if package is None:
        package = importlib.import_module("gta_mod_manager.plugins")

    registry = PluginRegistry()
    for module_info in pkgutil.iter_modules(package.__path__):
        if not module_info.ispkg:
            continue
        plugin = _load_plugin(f"{package.__name__}.{module_info.name}")
        if plugin is not None:
            registry.register(plugin)
    return registry


def _load_plugin(module_name: str) -> GamePlugin | None:
    """Import ``module_name`` and call its plugin factory."""
    for candidate in (module_name, f"{module_name}.plugin"):
        try:
            module = importlib.import_module(candidate)
        except ImportError as error:
            _LOGGER.debug("Skipping %s: %s", candidate, error)
            continue
        factory = getattr(module, PLUGIN_FACTORY_NAME, None)
        if factory is None:
            continue
        try:
            plugin = factory()
        except Exception as error:  # noqa: BLE001 - report, do not crash startup
            raise PluginLoadError(
                "Plugin factory raised an error", module=candidate, detail=str(error)
            ) from error
        if not isinstance(plugin, GamePlugin):
            raise PluginLoadError(
                "Plugin factory did not return a GamePlugin", module=candidate
            )
        return plugin
    return None
