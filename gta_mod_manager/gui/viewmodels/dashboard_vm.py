"""View model for the dashboard page."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.core.result import Result
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.component import DetectedComponent
from gta_mod_manager.models.essentials import EssentialsStatus
from gta_mod_manager.models.game_install import GameInstall, ValidationIssue
from gta_mod_manager.models.launch import LaunchOutcome, LaunchPreflightReport
from gta_mod_manager.services.backup_service import BackupService
from gta_mod_manager.services.essentials_service import EssentialsService
from gta_mod_manager.services.game_service import GameService, GameStatus
from gta_mod_manager.services.launch_service import LaunchService
from gta_mod_manager.services.library_service import LibraryService


@dataclass(frozen=True, slots=True)
class DashboardState:
    """Everything the dashboard renders in one shot."""

    install: GameInstall
    components: tuple[DetectedComponent, ...]
    missing: tuple[DetectedComponent, ...]
    issues: tuple[ValidationIssue, ...]
    installed_count: int
    snapshot_count: int
    mods_folder_exists: bool
    essentials: EssentialsStatus | None = None

    @property
    def platform_label(self) -> str:
        """Return the platform name for the header card."""
        return self.install.platform.display_name

    @property
    def version_label(self) -> str:
        """Return the game version, or a placeholder."""
        return self.install.version or "unknown"


class DashboardViewModel(ViewModel):
    """Loads and exposes the installation overview.

    Attributes:
        stateLoaded: Emitted with a :class:`DashboardState`.
        gameMissing: Emitted with a message when no installation was found.
        preflightReady: Emitted with a :class:`LaunchPreflightReport`.
        launchFinished: Emitted with a :class:`LaunchOutcome`.
        essentialsUpdated: Emitted after an essentials kit action.
    """

    stateLoaded = Signal(object)
    gameMissing = Signal(str)
    preflightReady = Signal(object)
    launchFinished = Signal(object)
    essentialsUpdated = Signal(object)

    def __init__(
        self,
        runner: TaskRunner,
        game: GameService,
        library: LibraryService,
        backups: BackupService,
        parent: QObject | None = None,
        launch: LaunchService | None = None,
        essentials: EssentialsService | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._game = game
        self._library = library
        self._backups = backups
        self._launch = launch
        self._essentials = essentials

    def refresh(self) -> None:
        """Reload the dashboard state in the background."""
        self.statusChanged.emit("Detecting GTA V installation...")
        self.run(self._load, self._publish)

    def choose_game_folder(self, folder: Path) -> None:
        """Select ``folder`` as the active installation, then refresh."""
        def work() -> Result[GameInstall]:
            return self._game.select(folder)

        self.run_result(work, lambda _install: self.refresh())

    def create_mods_folder(self) -> None:
        """Create ``<game>/mods`` for the active installation."""
        install = self._game.active
        if install is None:
            self.errorRaised.emit("Select a GTA V installation first")
            return

        def work() -> Path:
            return self._game.ensure_mods_folder(install)

        self.run(work, lambda _path: self.refresh())

    def install_essentials(self) -> None:
        """Auto-install redistributable essentials and refresh."""
        if self._essentials is None:
            self.errorRaised.emit("Essentials kit is unavailable")
            return
        self.statusChanged.emit("Installing Story Mode essentials...")

        def work() -> Result[EssentialsStatus]:
            return self._essentials.install_auto()

        def done(status: EssentialsStatus) -> None:
            self.essentialsUpdated.emit(status)
            self.statusChanged.emit(status.message)
            self.refresh()

        self.run_result(work, done, on_warnings=self._warn)

    def open_essentials_pages(self) -> None:
        """Open download pages for ScriptHookV / OpenIV."""
        if self._essentials is None:
            self.errorRaised.emit("Essentials kit is unavailable")
            return
        self.statusChanged.emit("Opening essentials download pages...")

        def work() -> Result[EssentialsStatus]:
            return self._essentials.open_manual_pages()

        def done(status: EssentialsStatus) -> None:
            self.essentialsUpdated.emit(status)
            self.statusChanged.emit(status.message)

        self.run_result(work, done, on_warnings=self._warn)

    def run_preflight(self) -> None:
        """Run the pre-launch health check and publish the report."""
        if self._launch is None:
            self.errorRaised.emit("Launch service is unavailable")
            return
        self.statusChanged.emit("Checking the game before launch...")

        def work() -> Result[LaunchPreflightReport]:
            return self._launch.preflight()

        self.run_result(work, self.preflightReady.emit)

    def launch_game(self, *, force: bool = False) -> None:
        """Start GTA V, optionally ignoring non-fatal / blocking findings."""
        if self._launch is None:
            self.errorRaised.emit("Launch service is unavailable")
            return
        self.statusChanged.emit("Starting Grand Theft Auto V...")

        def work() -> Result[LaunchOutcome]:
            return self._launch.launch(force=force)

        def done(outcome: LaunchOutcome) -> None:
            self.launchFinished.emit(outcome)
            self.statusChanged.emit(outcome.message)

        self.run_result(work, done)

    def _load(self) -> Result[DashboardState]:
        """Gather the dashboard state; runs on a worker thread."""
        status = self._game.status()
        if status.is_error:
            return Result.fail(status.error or "No installation", code=status.code)
        return Result.ok(self._to_state(status.unwrap()))

    def _to_state(self, status: GameStatus) -> DashboardState:
        """Convert a service status into the dashboard's own state object."""
        essentials: EssentialsStatus | None = None
        if self._essentials is not None:
            kit = self._essentials.status(status.install)
            if kit.is_ok:
                essentials = kit.unwrap()
        return DashboardState(
            install=status.install,
            components=status.components.components,
            missing=status.components.missing_dependencies,
            issues=status.validation.issues,
            installed_count=len(self._library.list_installed(status.install)),
            snapshot_count=len(self._backups.list_snapshots()),
            mods_folder_exists=status.install.mods_path.is_dir(),
            essentials=essentials,
        )

    def _publish(self, result: Result[DashboardState]) -> None:
        """Emit the loaded state, or report that no game was found."""
        if result.is_error:
            self.gameMissing.emit(result.error or "No GTA V installation found")
            self.statusChanged.emit("No installation selected")
            return
        state = result.unwrap()
        self.stateLoaded.emit(state)
        self.statusChanged.emit(f"Ready - {state.install.root_path}")

    def _warn(self, warnings: tuple[str, ...]) -> None:
        if warnings:
            self.statusChanged.emit(" | ".join(warnings))
