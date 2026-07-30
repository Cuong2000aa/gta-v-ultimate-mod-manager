"""Use-cases around backups: snapshot, undo, restore and history."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.backup.backup_engine import BackupEngine
from gta_mod_manager.core.events import EventBus, ModLibraryChangedEvent
from gta_mod_manager.core.exceptions import RestoreError, SnapshotNotFoundError
from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.core.protocols import ProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.models.backup_snapshot import BackupSnapshot
from gta_mod_manager.models.enums import FileAction
from gta_mod_manager.models.install_plan import InstallPlan
from gta_mod_manager.repository.backup_repository import JsonBackupRepository
from gta_mod_manager.utils import fs

_LOGGER = get_logger("services.backup")

#: Actions that edit a shared mods-folder ``.rpf`` in place. Their targets are
#: multi-gigabyte archives reverted member-by-member on uninstall, so they must
#: never be full-copied into a pre-install snapshot.
_IN_PLACE_ARCHIVE_ACTIONS = frozenset(
    {
        FileAction.RPF_IMPORT,
        FileAction.RPF_DLC_REGISTER,
        FileAction.RPF_PED_IMPORT,
    }
)


@dataclass(frozen=True, slots=True)
class SnapshotSummary:
    """A snapshot reduced to what the backup list displays."""

    snapshot: BackupSnapshot
    size_label: str

    @property
    def snapshot_id(self) -> str:
        """Return the snapshot identifier."""
        return self.snapshot.snapshot_id

    @property
    def label(self) -> str:
        """Return the display label of the snapshot."""
        return self.snapshot.display_label


class BackupService:
    """Wraps the backup engine with the workflows the UI offers."""

    def __init__(
        self,
        engine: BackupEngine,
        repository: JsonBackupRepository,
        bus: EventBus,
    ) -> None:
        self._engine = engine
        self._repository = repository
        self._bus = bus

    def snapshot_for_plan(
        self,
        plan: InstallPlan,
        operation_id: str,
        reporter: ProgressReporter | None = None,
    ) -> BackupSnapshot | None:
        """Snapshot everything ``plan`` is about to change.

        In-place edits of the huge shared archives (``x64e.rpf``,
        ``update.rpf`` via ``RPF_IMPORT`` / ``RPF_DLC_REGISTER`` /
        ``RPF_PED_IMPORT``) are skipped on purpose: those files are multiple
        gigabytes, shared by many mods, and uninstall already reverts them at
        the member level. Backing them up wholesale was what filled the disk.

        Plain writes — loose files, scripts, and freshly copied DLC packs — are
        still snapshotted so Undo keeps working.

        Returns:
            The snapshot, or ``None`` when nothing that needs a full-file
            backup is about to change.
        """
        targets = [
            operation.target_path
            for operation in plan.operations
            if operation.action is not FileAction.CREATE_DIRECTORY
            and operation.action not in _IN_PLACE_ARCHIVE_ACTIONS
        ]
        if not targets:
            _LOGGER.info(
                "Skipping pre-install snapshot for %s: only shared archives change",
                plan.display_name,
            )
            return None
        return self._engine.create(
            game_root=plan.game_root,
            paths=targets,
            reason=f"Before installing {plan.display_name}",
            mod_id=plan.package_id,
            operation_id=operation_id,
            reporter=reporter,
        )

    def snapshot_paths(
        self,
        game_root: Path,
        paths: tuple[Path, ...],
        reason: str,
        mod_id: str | None = None,
        reporter: ProgressReporter | None = None,
    ) -> BackupSnapshot:
        """Snapshot an explicit list of paths, e.g. before an uninstall."""
        return self._engine.create(
            game_root=game_root,
            paths=paths,
            reason=reason,
            mod_id=mod_id,
            reporter=reporter,
        )

    def restore(
        self, snapshot: BackupSnapshot, reporter: ProgressReporter | None = None
    ) -> int:
        """Restore ``snapshot`` and return how many paths were touched."""
        restored = self._engine.restore(snapshot, reporter)
        self._bus.publish(ModLibraryChangedEvent(reason="restored"))
        return restored

    def restore_by_id(
        self, snapshot_id: str, reporter: ProgressReporter | None = None
    ) -> Result[int]:
        """Restore the snapshot identified by ``snapshot_id``."""
        try:
            restored = self._engine.restore_by_id(snapshot_id, reporter)
        except SnapshotNotFoundError as error:
            return Result.fail(str(error), code="backup.not_found")
        except RestoreError as error:
            return Result.fail(str(error), code="backup.restore_failed")
        self._bus.publish(ModLibraryChangedEvent(reason="restored"))
        _LOGGER.info("Restored snapshot %s (%d path(s))", snapshot_id, restored)
        return Result.ok(restored)

    def undo_last(self, reporter: ProgressReporter | None = None) -> Result[int]:
        """Restore the most recent snapshot, i.e. undo the last operation."""
        snapshots = self._repository.list_snapshots()
        if not snapshots:
            return Result.fail("There is nothing to undo", code="backup.empty")
        return self.restore_by_id(snapshots[0].snapshot_id, reporter)

    def list_snapshots(self) -> tuple[SnapshotSummary, ...]:
        """Return every snapshot with a human readable size, newest first."""
        return tuple(
            SnapshotSummary(snapshot=item, size_label=fs.human_size(item.total_size))
            for item in self._repository.list_snapshots()
        )

    def history_for(self, mod_id: str) -> tuple[SnapshotSummary, ...]:
        """Return the version history of one mod."""
        return tuple(item for item in self.list_snapshots() if item.snapshot.mod_id == mod_id)

    def delete(self, snapshot_id: str) -> Result[None]:
        """Delete a snapshot and its stored data."""
        snapshot = self._repository.get_snapshot(snapshot_id)
        if snapshot is None:
            return Result.fail("Unknown snapshot", code="backup.not_found")
        self._engine.delete(snapshot)
        return Result.ok(None)

    def purge_all(self) -> int:
        """Delete every stored snapshot. Returns how many were removed."""
        snapshots = list(self._repository.list_snapshots())
        for snapshot in snapshots:
            self._engine.delete(snapshot)
        _LOGGER.info("Purged %d snapshot(s)", len(snapshots))
        return len(snapshots)
