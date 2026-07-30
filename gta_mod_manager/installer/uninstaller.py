"""Removal of an installed mod, using the exact file list it registered."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.core.exceptions import UninstallError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.progress import NullProgressReporter
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.utils import fs, hashing

_LOGGER = get_logger("installer.uninstall")


@dataclass(frozen=True, slots=True)
class UninstallOutcome:
    """Result of removing a mod.

    Attributes:
        removed: Files that were deleted.
        modified_externally: Files whose content no longer matched the record,
            so they were left alone.
        missing: Files that were already gone.
        directories_removed: Empty folders that were cleaned up.
    """

    removed: tuple[Path, ...] = ()
    modified_externally: tuple[Path, ...] = ()
    missing: tuple[Path, ...] = ()
    directories_removed: int = 0

    @property
    def is_clean(self) -> bool:
        """Return whether everything the mod owned could be removed."""
        return not self.modified_externally


class Uninstaller:
    """Deletes the files a mod installed, refusing to touch foreign changes.

    A file whose hash differs from the one recorded at install time was changed
    by the user or another mod. Deleting it would destroy work the manager does
    not own, so it is reported instead.
    """

    def __init__(self, *, verify_hashes: bool = True) -> None:
        self._verify_hashes = verify_hashes

    def uninstall(
        self,
        mod: InstalledMod,
        *,
        force: bool = False,
        reporter: ProgressReporter | None = None,
    ) -> UninstallOutcome:
        """Remove every file registered by ``mod``.

        Args:
            mod: The record describing what to remove.
            force: Delete files even when their content changed.
            reporter: Optional progress sink.

        Raises:
            UninstallError: When the record contains no files at all.
        """
        if not mod.installed_files:
            raise UninstallError(
                "This mod has no recorded files, so it cannot be removed safely",
                mod_id=mod.mod_id,
            )

        reporter = reporter or NullProgressReporter()
        reporter.start(mod.mod_id, f"Removing {mod.display_name}", total=mod.file_count)

        removed: list[Path] = []
        foreign: list[Path] = []
        missing: list[Path] = []

        for index, record in enumerate(mod.installed_files, start=1):
            target = record.target_path
            if not target.exists():
                missing.append(target)
            elif not force and self._was_modified(target, record.sha256):
                foreign.append(target)
            elif fs.delete_file(target):
                removed.append(target)
            reporter.advance(mod.mod_id, index)

        directories_removed = self._clean_directories(mod, removed)
        reporter.finish(mod.mod_id, f"Removed {mod.display_name}")
        _LOGGER.info(
            "Uninstalled %s: %d removed, %d kept (modified), %d already gone",
            mod.display_name,
            len(removed),
            len(foreign),
            len(missing),
        )

        return UninstallOutcome(
            removed=tuple(removed),
            modified_externally=tuple(foreign),
            missing=tuple(missing),
            directories_removed=directories_removed,
        )

    def _was_modified(self, target: Path, expected_hash: str | None) -> bool:
        """Return whether ``target`` differs from what was installed."""
        if not self._verify_hashes or expected_hash is None:
            return False
        try:
            return hashing.sha256_file(target) != expected_hash
        except OSError:
            return True

    @staticmethod
    def _clean_directories(mod: InstalledMod, removed: list[Path]) -> int:
        """Remove folders that the uninstallation left empty."""
        stop_at = mod.game_root
        count = 0
        for directory in sorted(
            {path.parent for path in removed}, key=lambda item: len(item.parts), reverse=True
        ):
            count += fs.remove_empty_directories(directory, stop_at)
        for directory in sorted(
            mod.created_directories, key=lambda item: len(item.parts), reverse=True
        ):
            count += fs.remove_empty_directories(directory, stop_at)
        return count
