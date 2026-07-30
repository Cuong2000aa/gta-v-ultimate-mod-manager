"""View model for the backup and restore pages."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.progress import EventBusProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.services.backup_service import BackupService, SnapshotSummary


class BackupViewModel(ViewModel):
    """Lists snapshots and performs restore, undo and delete.

    Attributes:
        snapshotsLoaded: Emitted with a tuple of :class:`SnapshotSummary`.
        restored: Emitted with the number of paths that were put back.
    """

    snapshotsLoaded = Signal(object)
    restored = Signal(int)

    def __init__(
        self,
        runner: TaskRunner,
        backups: BackupService,
        reporter: EventBusProgressReporter,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._backups = backups
        self._reporter = reporter

    def refresh(self) -> None:
        """Reload the snapshot list."""
        self.run(self._backups.list_snapshots, self._publish)

    def restore(self, snapshot_id: str) -> None:
        """Restore one snapshot."""
        self.statusChanged.emit("Restoring backup...")

        def work() -> Result[int]:
            return self._backups.restore_by_id(snapshot_id, self._reporter)

        self.run_result(work, self._on_restored)

    def undo_last(self) -> None:
        """Restore the most recent snapshot."""
        self.statusChanged.emit("Undoing the last operation...")

        def work() -> Result[int]:
            return self._backups.undo_last(self._reporter)

        self.run_result(work, self._on_restored)

    def delete(self, snapshot_id: str) -> None:
        """Delete one snapshot and its stored files."""
        def work() -> Result[None]:
            return self._backups.delete(snapshot_id)

        def done(_value: None) -> None:
            self.statusChanged.emit("Snapshot deleted")
            self.refresh()

        self.run_result(work, done)

    def _publish(self, snapshots: tuple[SnapshotSummary, ...]) -> None:
        """Emit the loaded snapshots."""
        self.snapshotsLoaded.emit(snapshots)
        self.statusChanged.emit(f"{len(snapshots)} backup(s) available")

    def _on_restored(self, count: int) -> None:
        """Emit the restore outcome and reload the list."""
        self.restored.emit(count)
        self.statusChanged.emit(f"Restored {count} path(s)")
        self.refresh()
