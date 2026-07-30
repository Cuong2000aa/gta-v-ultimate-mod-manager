"""View model for the Spawn Center page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QGuiApplication

from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.spawn import SpawnEntry, SpawnKind
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.services.spawn_catalog_service import SpawnCatalogService


class SpawnViewModel(ViewModel):
    """Loads and filters spawn codes from installed mods."""

    entriesLoaded = Signal(object)
    copied = Signal(str)

    def __init__(
        self,
        runner: TaskRunner,
        catalog: SpawnCatalogService,
        game: GameService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._catalog = catalog
        self._game = game
        self._query = ""
        self._kind: SpawnKind | None = None
        self._entries: tuple[SpawnEntry, ...] = ()

    @property
    def entries(self) -> tuple[SpawnEntry, ...]:
        """Return the last loaded entries."""
        return self._entries

    def refresh(self) -> None:
        """Reload spawn codes for the active installation."""
        self.statusChanged.emit("Loading spawn codes...")

        def work() -> tuple[SpawnEntry, ...]:
            return self._catalog.list_entries(
                self._game.active,
                query=self._query,
                kind=self._kind,
            )

        def done(entries: tuple[SpawnEntry, ...]) -> None:
            self._entries = entries
            self.entriesLoaded.emit(entries)
            self.statusChanged.emit(f"{len(entries)} spawn code(s)")

        self.run(work, done)

    def set_query(self, query: str) -> None:
        """Filter by spawn code or mod name."""
        self._query = query
        self.refresh()

    def set_kind_filter(self, kind: SpawnKind | None) -> None:
        """Filter by vehicle / ped / all."""
        self._kind = kind
        self.refresh()

    def apply_filters(self, *, query: str, kind: SpawnKind | None) -> None:
        """Update both filters and reload once."""
        self._query = query
        self._kind = kind
        self.refresh()

    def copy_code(self, code: str) -> None:
        """Copy ``code`` to the system clipboard."""
        clipboard = QGuiApplication.clipboard()
        if clipboard is None:
            self.errorRaised.emit("Clipboard is unavailable")
            return
        clipboard.setText(code)
        self.copied.emit(code)
        self.statusChanged.emit(f"Copied: {code}")
