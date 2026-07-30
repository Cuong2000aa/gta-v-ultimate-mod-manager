"""View model for the conflict center."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.services.conflict_service import ConflictGroup, ConflictService
from gta_mod_manager.services.game_service import GameService


class ConflictViewModel(ViewModel):
    """Audits the installation and exposes grouped conflicts.

    Attributes:
        groupsLoaded: Emitted with a tuple of :class:`ConflictGroup`.
    """

    groupsLoaded = Signal(object)

    def __init__(
        self,
        runner: TaskRunner,
        conflicts: ConflictService,
        game: GameService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._conflicts = conflicts
        self._game = game

    def refresh(self) -> None:
        """Re-run the audit in the background."""
        install = self._game.active
        if install is None:
            self.groupsLoaded.emit(())
            self.statusChanged.emit("Select a GTA V installation first")
            return

        self.statusChanged.emit("Scanning for conflicts...")

        def work() -> tuple[ConflictGroup, ...]:
            return self._conflicts.grouped(install)

        self.run(work, self._publish)

    def _publish(self, groups: tuple[ConflictGroup, ...]) -> None:
        """Emit the grouped conflicts and summarise them."""
        self.groupsLoaded.emit(groups)
        total = sum(len(group.conflicts) for group in groups)
        blocking = sum(
            1
            for group in groups
            for conflict in group.conflicts
            if conflict.is_blocking
        )
        self.statusChanged.emit(
            "No conflicts detected"
            if total == 0
            else f"{total} conflict(s), {blocking} blocking"
        )
