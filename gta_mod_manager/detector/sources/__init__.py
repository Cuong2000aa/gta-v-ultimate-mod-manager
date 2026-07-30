"""Individual strategies used to locate GTA V installations."""

from gta_mod_manager.detector.sources.base import DetectionSource
from gta_mod_manager.detector.sources.common_paths_source import CommonPathsSource
from gta_mod_manager.detector.sources.epic_source import EpicSource
from gta_mod_manager.detector.sources.registry_source import (
    RockstarRegistrySource,
    UninstallRegistrySource,
)
from gta_mod_manager.detector.sources.steam_source import SteamSource

__all__ = [
    "CommonPathsSource",
    "DetectionSource",
    "EpicSource",
    "RockstarRegistrySource",
    "SteamSource",
    "UninstallRegistrySource",
]


def default_sources() -> tuple[DetectionSource, ...]:
    """Return the detection sources used by the application, in priority order."""
    return (
        RockstarRegistrySource(),
        SteamSource(),
        EpicSource(),
        UninstallRegistrySource(),
        CommonPathsSource(),
    )
