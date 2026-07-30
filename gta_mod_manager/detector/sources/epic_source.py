"""Detection through the Epic Games Launcher manifest files."""

from __future__ import annotations

import json
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.detector.sources.base import DetectionSource
from gta_mod_manager.models.enums import GamePlatform

_LOGGER = get_logger("detector.epic")

_TITLE_TOKENS = ("grand theft auto v", "gtav")


class EpicSource(DetectionSource):
    """Reads ``.item`` manifests written by the Epic Games Launcher."""

    source_name = "epic"
    platform = GamePlatform.EPIC

    def __init__(self, manifest_dir: Path | None = None) -> None:
        self._manifest_dir = manifest_dir or Path(constants.EPIC_MANIFEST_DIR)

    def candidate_paths(self) -> tuple[Path, ...]:
        """Return the install locations of GTA V manifests."""
        if not self._manifest_dir.is_dir():
            return ()
        found: list[Path] = []
        for manifest in self._manifest_dir.glob("*.item"):
            location = self._read_manifest(manifest)
            if location is not None:
                found.append(location)
        return tuple(found)

    @staticmethod
    def _read_manifest(manifest: Path) -> Path | None:
        """Return the install location when ``manifest`` describes GTA V."""
        try:
            payload = json.loads(manifest.read_text(encoding="utf-8", errors="replace"))
        except (OSError, json.JSONDecodeError) as error:
            _LOGGER.debug("Skipping unreadable Epic manifest %s: %s", manifest, error)
            return None
        if not isinstance(payload, dict):
            return None

        app_name = str(payload.get("AppName", ""))
        display_name = str(payload.get("DisplayName", "")).lower()
        matches_id = app_name in constants.EPIC_GTA_V_APP_NAMES
        matches_title = any(token in display_name for token in _TITLE_TOKENS)
        if not (matches_id or matches_title):
            return None

        location = payload.get("InstallLocation")
        return Path(str(location)) if location else None
