"""Plugin architecture: the core delegates all game knowledge to plugins."""

from gta_mod_manager.plugins.contracts import (
    GamePlugin,
    PlanRequest,
    PluginMetadata,
    TargetDecision,
)
from gta_mod_manager.plugins.registry import PluginRegistry, discover_plugins

__all__ = [
    "GamePlugin",
    "PlanRequest",
    "PluginMetadata",
    "PluginRegistry",
    "TargetDecision",
    "discover_plugins",
]
