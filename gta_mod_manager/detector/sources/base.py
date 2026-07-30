"""Contract shared by every game detection source."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.utils import fs


class DetectionSource(ABC):
    """One strategy for finding GTA V installations.

    Sources are intentionally dumb: they propose candidate folders. Validation
    and de-duplication happen once, in
    :class:`~gta_mod_manager.detector.game_detector.GameDetector`.
    """

    #: Identifier reported in :attr:`GameInstall.detected_by`.
    source_name: str = "unknown"

    #: Platform every candidate of this source belongs to.
    platform: GamePlatform = GamePlatform.UNKNOWN

    @abstractmethod
    def candidate_paths(self) -> tuple[Path, ...]:
        """Return folders that might contain a GTA V installation."""

    def build_install(self, root: Path) -> GameInstall:
        """Wrap ``root`` into a :class:`GameInstall` for this source."""
        executable = root / constants.PRIMARY_EXECUTABLE
        return GameInstall(
            game_id=constants.GAME_ID_GTA_V,
            root_path=fs.normalise(root),
            platform=self.platform,
            executable=executable if executable.is_file() else None,
            detected_by=self.source_name,
        )
