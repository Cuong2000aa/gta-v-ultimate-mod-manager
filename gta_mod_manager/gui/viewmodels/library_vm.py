"""View model for the installed-mods page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.progress import EventBusProgressReporter
from gta_mod_manager.core.result import Result
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.services.library_service import LibraryService, ModSummary


class LibraryViewModel(ViewModel):
    """Lists, searches, verifies and removes installed mods.

    Attributes:
        modsLoaded: Emitted with a tuple of :class:`ModSummary`.
        modRemoved: Emitted with the identifier of the removed mod.
        verificationDone: Emitted with ``(mod_id, problems)``.
    """

    modsLoaded = Signal(object)
    modRemoved = Signal(str)
    verificationDone = Signal(str, object)

    def __init__(
        self,
        runner: TaskRunner,
        library: LibraryService,
        game: GameService,
        reporter: EventBusProgressReporter | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._library = library
        self._game = game
        self._reporter = reporter
        self._query = ""

    @property
    def query(self) -> str:
        """Return the active search text."""
        return self._query

    def refresh(self) -> None:
        """Reload the mod list using the current search text."""
        query = self._query

        def work() -> tuple[ModSummary, ...]:
            return self._library.search(query, self._game.active)

        self.run(work, self._publish)

    def search(self, query: str) -> None:
        """Change the search text and reload."""
        self._query = query
        self.refresh()

    def uninstall(self, mod_id: str, *, force: bool = False) -> None:
        """Remove a mod and refresh the list."""
        self.statusChanged.emit("Removing mod...")

        def work() -> Result[int]:
            return self._library.uninstall(mod_id, force=force, reporter=self._reporter)

        def done(removed: int) -> None:
            self.statusChanged.emit(f"Removed {removed} file(s)")
            self.modRemoved.emit(mod_id)
            self.refresh()

        self.run_result(work, done, on_warnings=self._warn)

    def verify(self, mod_id: str) -> None:
        """Check whether a mod's files are still intact."""
        def work() -> Result[tuple[str, ...]]:
            return self._library.verify(mod_id)

        def done(problems: tuple[str, ...]) -> None:
            self.verificationDone.emit(mod_id, problems)
            self.statusChanged.emit(
                "All files are intact" if not problems else f"{len(problems)} problem(s) found"
            )
            self.refresh()

        self.run_result(work, done)

    def set_enabled(self, mod_id: str, enabled: bool) -> None:
        """Enable or disable a mod in the library."""
        def work() -> Result[InstalledMod]:
            return self._library.set_enabled(mod_id, enabled)

        self.run_result(work, lambda _mod: self.refresh())

    def _publish(self, summaries: tuple[ModSummary, ...]) -> None:
        """Emit the loaded list and a short status line."""
        self.modsLoaded.emit(summaries)
        self.statusChanged.emit(f"{len(summaries)} mod(s) installed")

    def _warn(self, warnings: tuple[str, ...]) -> None:
        """Surface warnings from a removal."""
        if warnings:
            self.statusChanged.emit(" | ".join(warnings))
