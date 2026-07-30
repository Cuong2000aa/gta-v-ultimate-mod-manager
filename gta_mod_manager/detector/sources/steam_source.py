"""Detection through Steam, including secondary library folders."""

from __future__ import annotations

import re
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.detector.sources.base import DetectionSource
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.utils import windows

_LOGGER = get_logger("detector.steam")

#: Matches ``"path"    "D:\\SteamLibrary"`` inside ``libraryfolders.vdf``.
_LIBRARY_PATH_PATTERN = re.compile(r'"path"\s+"([^"]+)"', re.IGNORECASE)


class SteamSource(DetectionSource):
    """Finds GTA V in every configured Steam library."""

    source_name = "steam"
    platform = GamePlatform.STEAM

    def candidate_paths(self) -> tuple[Path, ...]:
        """Return the GTA V folder of each Steam library that has one."""
        candidates: list[Path] = []
        for library in self._steam_libraries():
            candidates.append(library.joinpath(*constants.STEAM_DEFAULT_GAME_FOLDER.split("/")))
        return tuple(candidates)

    def _steam_libraries(self) -> tuple[Path, ...]:
        """Return every Steam library root known to the client."""
        roots: list[Path] = []
        install_root = self._steam_install_root()
        if install_root is not None:
            roots.append(install_root)
            roots.extend(self._parse_library_folders(install_root))
        deduplicated: dict[str, Path] = {}
        for root in roots:
            deduplicated.setdefault(str(root).lower(), root)
        return tuple(deduplicated.values())

    @staticmethod
    def _steam_install_root() -> Path | None:
        """Return the Steam client installation folder."""
        for hive, key_path, value_name in constants.REG_STEAM_PATHS:
            value = windows.read_registry_value(hive, key_path, value_name)
            if value:
                path = Path(value)
                if path.exists():
                    return path
        return None

    @staticmethod
    def _parse_library_folders(steam_root: Path) -> tuple[Path, ...]:
        """Return additional libraries declared in ``libraryfolders.vdf``.

        The file is parsed with a regular expression rather than a full VDF
        parser so the detector keeps working when the optional ``vdf``
        dependency is absent.
        """
        manifest = steam_root.joinpath(*constants.STEAM_LIBRARY_MANIFEST.split("/"))
        if not manifest.is_file():
            return ()
        try:
            text = manifest.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            _LOGGER.debug("Could not read %s: %s", manifest, error)
            return ()
        return tuple(
            Path(match.replace("\\\\", "\\")) for match in _LIBRARY_PATH_PATTERN.findall(text)
        )
