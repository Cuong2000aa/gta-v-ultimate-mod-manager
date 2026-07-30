"""Detection through the Rockstar Games registry keys."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.detector.sources.base import DetectionSource
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.utils import windows


class RockstarRegistrySource(DetectionSource):
    """Reads ``InstallFolder`` from the Rockstar Games registry keys."""

    source_name = "rockstar-registry"
    platform = GamePlatform.ROCKSTAR

    def candidate_paths(self) -> tuple[Path, ...]:
        """Return the install folders declared by the Rockstar Launcher."""
        found: list[Path] = []
        for hive, key_path, value_name in constants.REG_ROCKSTAR_PATHS:
            value = windows.read_registry_value(hive, key_path, value_name)
            if value:
                found.append(Path(value))
        return tuple(found)


class UninstallRegistrySource(DetectionSource):
    """Scans the Windows uninstall entries for a GTA V install location.

    This catches setups the dedicated launcher keys miss, for example games
    moved to another drive after installation.
    """

    source_name = "uninstall-registry"
    platform = GamePlatform.UNKNOWN

    _MATCHING_DISPLAY_NAMES = ("grand theft auto v", "gtav")

    def candidate_paths(self) -> tuple[Path, ...]:
        """Return install locations of uninstall entries naming GTA V."""
        found: list[Path] = []
        for hive, root_key in constants.REG_UNINSTALL_ROOTS:
            for subkey in windows.iter_registry_subkeys(hive, root_key):
                key_path = f"{root_key}\\{subkey}"
                display_name = windows.read_registry_value(hive, key_path, "DisplayName")
                if not display_name:
                    continue
                lowered = display_name.lower()
                if not any(token in lowered for token in self._MATCHING_DISPLAY_NAMES):
                    continue
                location = windows.read_registry_value(hive, key_path, "InstallLocation")
                if location:
                    found.append(Path(location))
        return tuple(found)
