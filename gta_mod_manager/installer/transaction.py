"""A journalled transaction around a sequence of file operations.

The journal records what actually happened, in order. If any step fails the
transaction replays the journal backwards, so the game folder returns to the
state it was in before the installation started - even when the backup engine
is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from types import TracebackType

from gta_mod_manager.core.exceptions import RollbackError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.enums import FileAction
from gta_mod_manager.utils import fs

_LOGGER = get_logger("installer.transaction")


@dataclass(frozen=True, slots=True)
class JournalEntry:
    """One completed step, with everything needed to undo it.

    Attributes:
        action: What was done.
        target: Path that was created, replaced or removed.
        replaced_backup: Temporary copy of the file that was overwritten.
    """

    action: FileAction
    target: Path
    replaced_backup: Path | None = None


@dataclass
class Transaction:
    """Collects journal entries and can undo them in reverse order.

    Attributes:
        scratch_dir: Folder holding copies of overwritten files.
    """

    scratch_dir: Path
    _entries: list[JournalEntry] = field(default_factory=list, repr=False)
    _committed: bool = field(default=False, repr=False)

    @property
    def entries(self) -> tuple[JournalEntry, ...]:
        """Return the journal in execution order."""
        return tuple(self._entries)

    @property
    def is_committed(self) -> bool:
        """Return whether the transaction was committed."""
        return self._committed

    def record(self, entry: JournalEntry) -> None:
        """Append ``entry`` to the journal."""
        self._entries.append(entry)

    def stash_existing(self, target: Path) -> Path | None:
        """Copy ``target`` into the scratch folder before it is replaced.

        Returns:
            The scratch copy, or ``None`` when ``target`` did not exist.
        """
        if not target.is_file():
            return None
        scratch = fs.unique_path(self.scratch_dir / f"{len(self._entries):05d}_{target.name}")
        fs.copy_file(target, scratch)
        return scratch

    def commit(self) -> None:
        """Mark the transaction successful and drop the scratch folder."""
        self._committed = True
        fs.delete_tree(self.scratch_dir)
        _LOGGER.debug("Committed transaction with %d entry(ies)", len(self._entries))

    def rollback(self) -> int:
        """Undo every journalled step, newest first.

        Returns:
            The number of steps that were undone.

        Raises:
            RollbackError: When at least one step could not be undone; the
                remaining steps are still attempted first.
        """
        undone = 0
        failures: list[str] = []
        for entry in reversed(self._entries):
            try:
                if self._undo(entry):
                    undone += 1
            except Exception as error:  # noqa: BLE001 - continue undoing the rest
                failures.append(f"{entry.target}: {error}")
        self._entries.clear()
        _LOGGER.warning("Rolled back %d step(s)", undone)
        if failures:
            raise RollbackError(
                "The installation was rolled back, but some steps failed",
                failures=failures,
            )
        return undone

    @staticmethod
    def _undo(entry: JournalEntry) -> bool:
        """Undo one journal entry."""
        if entry.action is FileAction.CREATE_DIRECTORY:
            if entry.target.is_dir() and not any(entry.target.iterdir()):
                entry.target.rmdir()
                return True
            return False

        if entry.replaced_backup is not None and entry.replaced_backup.is_file():
            fs.copy_file(entry.replaced_backup, entry.target)
            return True

        return fs.delete_file(entry.target)

    def __enter__(self) -> "Transaction":
        """Create the scratch folder and return this transaction."""
        fs.ensure_directory(self.scratch_dir)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Roll back automatically when the block exits with an exception."""
        if exc_type is not None and not self._committed:
            self.rollback()
        elif not self._committed:
            fs.delete_tree(self.scratch_dir)
