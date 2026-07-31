"""View model for the managed zombie game mode."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.launch import LaunchOutcome
from gta_mod_manager.models.zombie import ZombieModeStatus
from gta_mod_manager.services.launch_service import LaunchService
from gta_mod_manager.services.zombie_mode_service import ZombieModeService


class ZombieViewModel(ViewModel):
    """Install, remove and launch Simple Zombies Reborn."""

    statusLoaded = Signal(object)
    launchFinished = Signal(object)

    def __init__(
        self,
        runner: TaskRunner,
        zombie: ZombieModeService,
        launch: LaunchService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._zombie = zombie
        self._launch = launch
        self._status: ZombieModeStatus | None = None

    @property
    def status(self) -> ZombieModeStatus | None:
        """Return the last loaded state."""
        return self._status

    def refresh(self) -> None:
        """Reload zombie-mode readiness."""
        self.statusChanged.emit("Đang kiểm tra chế độ Zombie...")

        def work() -> ZombieModeStatus:
            result = self._zombie.status()
            if result.is_error:
                raise RuntimeError(result.error or "Không kiểm tra được chế độ Zombie")
            return result.unwrap()

        self.run(work, self._on_status)

    def install(self) -> None:
        """Install or update the pinned official release."""
        self.statusChanged.emit("Đang tải, xác minh và cài Simple Zombies Reborn...")

        def work() -> ZombieModeStatus:
            result = self._zombie.install()
            if result.is_error:
                raise RuntimeError(result.error or "Cài chế độ Zombie thất bại")
            return result.unwrap()

        self.run(work, self._on_status)

    def uninstall(self) -> None:
        """Back up and remove the managed zombie mode."""
        self.statusChanged.emit("Đang sao lưu và gỡ chế độ Zombie...")

        def work() -> ZombieModeStatus:
            result = self._zombie.uninstall()
            if result.is_error:
                raise RuntimeError(result.error or "Gỡ chế độ Zombie thất bại")
            return result.unwrap()

        self.run(work, self._on_status)

    def launch_game(self) -> None:
        """Start GTA V through its platform launcher."""
        self.statusChanged.emit("Đang mở GTA V...")

        def work() -> LaunchOutcome:
            result = self._launch.launch()
            if result.is_error:
                raise RuntimeError(result.error or "Không mở được GTA V")
            return result.unwrap()

        def done(outcome: LaunchOutcome) -> None:
            self.launchFinished.emit(outcome)
            self.statusChanged.emit(outcome.message)

        self.run(work, done)

    def _on_status(self, status: ZombieModeStatus) -> None:
        self._status = status
        self.statusLoaded.emit(status)
        self.statusChanged.emit(status.message)
