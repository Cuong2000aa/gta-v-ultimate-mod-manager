"""View model for the Graphics / NCCVision page."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.graphics import GraphicsLevel, GraphicsStatus
from gta_mod_manager.services.game_service import GameService
from gta_mod_manager.services.graphics_service import GraphicsService


class GraphicsViewModel(ViewModel):
    """Install, switch level, or remove NCCVision."""

    statusLoaded = Signal(object)

    def __init__(
        self,
        runner: TaskRunner,
        graphics: GraphicsService,
        game: GameService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._graphics = graphics
        self._game = game
        self._status: GraphicsStatus | None = None
        self._selected = GraphicsLevel.CINEMATIC_DETAIL_AA

    @property
    def selected_level(self) -> GraphicsLevel:
        """Return the level chosen in the UI."""
        return self._selected

    @property
    def status(self) -> GraphicsStatus | None:
        """Return the last known install status."""
        return self._status

    def refresh(self) -> None:
        """Reload status for the active game."""
        self.statusChanged.emit("Checking graphics pack...")

        def work() -> GraphicsStatus:
            result = self._graphics.status()
            if result.is_error:
                raise RuntimeError(result.error or "Status failed")
            return result.unwrap()

        def done(status: GraphicsStatus) -> None:
            self._status = status
            if status.level is not None:
                self._selected = status.level
            self.statusLoaded.emit(status)
            self.statusChanged.emit(status.message)

        self.run(work, done)

    def install(self) -> None:
        """Install the single NCCVision Ultimate profile."""
        level = GraphicsLevel.CINEMATIC_DETAIL_AA
        self.statusChanged.emit("Installing NCCVision Ultimate...")

        def work() -> GraphicsStatus:
            result = self._graphics.install(level)
            if result.is_error:
                raise RuntimeError(result.error or "Install failed")
            return result.unwrap()

        self.run(work, self._on_status)

    def uninstall(self) -> None:
        """Remove NCCVision from the game folder."""
        self.statusChanged.emit("Removing NCCVision...")

        def work() -> GraphicsStatus:
            result = self._graphics.uninstall()
            if result.is_error:
                raise RuntimeError(result.error or "Uninstall failed")
            return result.unwrap()

        self.run(work, self._on_status)

    def install_road_2k(self) -> None:
        """Download and install the optional selective 2K road add-on."""
        self.statusChanged.emit("Đang tải và cài texture đường 2K an toàn...")

        def work() -> str:
            result = self._graphics.install_road_2k()
            if result.is_error:
                raise RuntimeError(result.error or "2K road install failed")
            return result.unwrap()

        self.run(work, self.statusChanged.emit)

    def uninstall_road_2k(self) -> None:
        """Restore the stock road textures."""
        self.statusChanged.emit("Đang khôi phục texture đường gốc...")

        def work() -> str:
            result = self._graphics.uninstall_road_2k()
            if result.is_error:
                raise RuntimeError(result.error or "2K road uninstall failed")
            return result.unwrap()

        self.run(work, self.statusChanged.emit)

    def _on_status(self, status: GraphicsStatus) -> None:
        self._status = status
        if status.level is not None:
            self._selected = status.level
        self.statusLoaded.emit(status)
        self.statusChanged.emit(status.message)
