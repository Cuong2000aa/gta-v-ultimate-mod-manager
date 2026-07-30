"""Detection by probing the folders GTA V is conventionally installed into."""

from __future__ import annotations

import string
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.detector.sources.base import DetectionSource
from gta_mod_manager.models.enums import GamePlatform

#: Folder layouts probed on every fixed drive of the machine.
_DRIVE_RELATIVE_CANDIDATES: tuple[str, ...] = (
    "Games/Grand Theft Auto V",
    "Grand Theft Auto V",
    "SteamLibrary/steamapps/common/Grand Theft Auto V",
    "Steam/steamapps/common/Grand Theft Auto V",
    "Program Files/Rockstar Games/Grand Theft Auto V",
    "Program Files/Epic Games/GTAV",
    "Epic Games/GTAV",
    "Rockstar Games/Grand Theft Auto V",
)


class CommonPathsSource(DetectionSource):
    """Probes well known install locations across all available drives."""

    source_name = "common-paths"
    platform = GamePlatform.UNKNOWN

    def __init__(self, extra_paths: tuple[Path, ...] = ()) -> None:
        self._extra_paths = extra_paths

    def candidate_paths(self) -> tuple[Path, ...]:
        """Return every conventional folder that currently exists."""
        candidates: list[Path] = [Path(item) for item in constants.COMMON_INSTALL_FOLDERS]
        candidates.extend(self._extra_paths)
        for drive in self._available_drives():
            candidates.extend(
                drive.joinpath(*relative.split("/")) for relative in _DRIVE_RELATIVE_CANDIDATES
            )
        return tuple(candidates)

    @staticmethod
    def _available_drives() -> tuple[Path, ...]:
        """Return the roots of every drive letter that is currently mounted."""
        drives: list[Path] = []
        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:/")
            try:
                if root.exists():
                    drives.append(root)
            except OSError:  # pragma: no cover - disconnected network drives
                continue
        return tuple(drives)
