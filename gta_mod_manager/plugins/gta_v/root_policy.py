"""The whitelist that enforces the absolute safety rule.

Only a small, explicitly enumerated set of files and folders may be installed
into the game root. Everything else belongs inside ``<game>/mods``. Original
game archives and executables are never writable, not even with a backup.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath

from gta_mod_manager.core import constants
from gta_mod_manager.models.enums import InstallTarget
from gta_mod_manager.utils import patterns


@dataclass(frozen=True, slots=True)
class RootVerdict:
    """Outcome of asking the policy about one file.

    Attributes:
        allowed: Whether the file may be written to the game root.
        target: Which zone it belongs to when allowed.
        reason: Explanation for the preview dialog and the log.
    """

    allowed: bool
    target: InstallTarget | None = None
    reason: str = ""


class RootInstallPolicy:
    """Decides whether a file may live outside the ``mods`` folder."""

    def __init__(
        self,
        file_patterns: tuple[str, ...] = constants.ALLOWED_ROOT_FILE_PATTERNS,
        directories: tuple[str, ...] = constants.ALLOWED_ROOT_DIRECTORIES,
        protected_files: frozenset[str] = constants.PROTECTED_ROOT_FILES,
    ) -> None:
        self._file_patterns = file_patterns
        self._directories = directories
        self._protected_files = protected_files

    def is_protected(self, relative_path: PurePosixPath) -> bool:
        """Return whether ``relative_path`` targets an original game file.

        Both the game's own executables/archives and any ``.rpf`` outside the
        ``mods`` folder are protected.
        """
        name = relative_path.name.lower()
        if name in self._protected_files:
            return True
        if relative_path.suffix.lower() == constants.PROTECTED_ARCHIVE_SUFFIX:
            return constants.MODS_FOLDER_NAME not in {
                part.lower() for part in relative_path.parts
            }
        return False

    def allows_file(self, file_name: str) -> bool:
        """Return whether a loose file with this name may sit in the root."""
        if file_name.lower() in self._protected_files:
            return False
        return patterns.matches_any(file_name, self._file_patterns)

    def allowed_directory(self, directory_name: str) -> str | None:
        """Return the canonical root folder name, or ``None`` when disallowed."""
        lowered = directory_name.lower()
        for candidate in self._directories:
            if candidate.lower() == lowered:
                return directory_name
        return None

    def evaluate(self, relative_path: PurePosixPath) -> RootVerdict:
        """Return the verdict for installing ``relative_path`` into the root."""
        if self.is_protected(relative_path):
            return RootVerdict(
                allowed=False,
                reason=f"{relative_path.name} is an original game file and is never modified",
            )

        first = relative_path.parts[0] if len(relative_path.parts) > 1 else None
        if first is not None:
            canonical = self.allowed_directory(first)
            if canonical is not None:
                return RootVerdict(
                    allowed=True,
                    target=self._zone_for_directory(canonical),
                    reason=f"'{canonical}' is a whitelisted root folder",
                )

        if len(relative_path.parts) == 1 and self.allows_file(relative_path.name):
            return RootVerdict(
                allowed=True,
                target=InstallTarget.GAME_ROOT,
                reason=f"{relative_path.name} matches the root install whitelist",
            )

        return RootVerdict(
            allowed=False,
            reason="Not on the root whitelist, so it belongs inside the mods folder",
        )

    @staticmethod
    def _zone_for_directory(directory_name: str) -> InstallTarget:
        """Map a whitelisted folder onto its install zone."""
        lowered = directory_name.lower()
        if lowered == constants.SCRIPTS_FOLDER_NAME:
            return InstallTarget.SCRIPTS_FOLDER
        if lowered == constants.LML_FOLDER_NAME:
            return InstallTarget.LML_FOLDER
        return InstallTarget.GAME_ROOT
