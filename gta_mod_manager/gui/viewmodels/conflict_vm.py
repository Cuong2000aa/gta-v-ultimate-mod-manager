"""View model for the conflict center."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.result import Result
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.services.conflict_service import ConflictGroup, ConflictService
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.services.library_service import LibraryService


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
        library: LibraryService | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._conflicts = conflicts
        self._game = game
        self._library = library

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

    def disable_mods(self, mod_ids: tuple[str, ...]) -> None:
        """Physically disable the listed mods, then refresh the audit."""
        if self._library is None:
            self.errorRaised.emit("Library service is unavailable")
            return
        unique = tuple(dict.fromkeys(mod_id for mod_id in mod_ids if mod_id))
        if not unique:
            self.errorRaised.emit("No mod id available for this conflict")
            return
        self.statusChanged.emit("Disabling conflicting mods...")

        def work() -> Result[str]:
            disabled: list[str] = []
            errors: list[str] = []
            for mod_id in unique:
                current = self._library.get(mod_id)
                if current is not None and current.status is ModStatus.DISABLED:
                    continue
                result = self._library.set_enabled(mod_id, False)
                if result.is_error:
                    errors.append(result.error or mod_id)
                else:
                    disabled.append(result.unwrap().display_name)
            if errors and not disabled:
                return Result.fail("; ".join(errors), code="conflicts.disable_failed")
            message = (
                f"Disabled {len(disabled)} mod(s): {', '.join(disabled)}"
                if disabled
                else "No mods needed disabling"
            )
            if errors:
                return Result(value=message, warnings=tuple(errors))
            return Result.ok(message)

        def done(message: str) -> None:
            self.statusChanged.emit(message)
            self.refresh()

        self.run_result(
            work,
            done,
            on_warnings=lambda warnings: self.statusChanged.emit(" | ".join(warnings)),
        )

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
