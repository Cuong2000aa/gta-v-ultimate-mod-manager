"""Entities describing a detected game installation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.models.enums import GamePlatform


@dataclass(frozen=True, slots=True)
class GameInstall:
    """A GTA V installation found on disk.

    Attributes:
        game_id: Identifier of the plugin that owns this installation.
        root_path: Folder containing ``GTA5.exe``.
        platform: Distribution platform the installation belongs to.
        executable: Resolved main executable, when present.
        version: Executable file version, when it could be read.
        detected_by: Name of the detection source that produced this entry.
    """

    game_id: str
    root_path: Path
    platform: GamePlatform = GamePlatform.UNKNOWN
    executable: Path | None = None
    version: str | None = None
    detected_by: str = "unknown"

    @property
    def mods_path(self) -> Path:
        """Return the ``mods`` folder used for safe installations."""
        return self.root_path / constants.MODS_FOLDER_NAME

    @property
    def scripts_path(self) -> Path:
        """Return the ``scripts`` folder used by .NET/ASI scripts."""
        return self.root_path / constants.SCRIPTS_FOLDER_NAME

    @property
    def dlc_packs_path(self) -> Path:
        """Return the add-on DLC pack folder inside ``mods``."""
        return self.mods_path.joinpath(*constants.DLC_PACKS_RELATIVE.split("/"))

    @property
    def display_name(self) -> str:
        """Return a label combining platform and folder name."""
        return f"{constants.GAME_TITLE_GTA_V} ({self.platform.display_name})"

    def with_version(self, version: str | None) -> "GameInstall":
        """Return a copy carrying the supplied executable version."""
        return GameInstall(
            game_id=self.game_id,
            root_path=self.root_path,
            platform=self.platform,
            executable=self.executable,
            version=version,
            detected_by=self.detected_by,
        )


@dataclass(frozen=True, slots=True)
class ValidationIssue:
    """A single problem found while validating an installation or plan."""

    code: str
    message: str
    is_fatal: bool = False
    path: Path | None = None


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """Aggregated outcome of a validation pass."""

    issues: tuple[ValidationIssue, ...] = field(default_factory=tuple)

    @property
    def is_valid(self) -> bool:
        """Return ``True`` when no fatal issue was recorded."""
        return not any(issue.is_fatal for issue in self.issues)

    @property
    def fatal_issues(self) -> tuple[ValidationIssue, ...]:
        """Return only the issues that block the operation."""
        return tuple(issue for issue in self.issues if issue.is_fatal)

    @property
    def warnings(self) -> tuple[ValidationIssue, ...]:
        """Return only the non-fatal issues."""
        return tuple(issue for issue in self.issues if not issue.is_fatal)

    def merged_with(self, other: "ValidationReport") -> "ValidationReport":
        """Return a report containing the issues of both reports."""
        return ValidationReport(issues=(*self.issues, *other.issues))
