"""View model for the settings page."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.models.game_install import GameInstall, ValidationReport
from gta_mod_manager.models.settings import AppSettings
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.services.crash_monitor_service import CrashMonitorService
from gta_mod_manager.services.data_directory_service import (
    DataDirectoryMigration,
    DataDirectoryService,
)
from gta_mod_manager.services.game_service import GameService


class SettingsViewModel(ViewModel):
    """Reads and writes the user preferences.

    Attributes:
        settingsLoaded: Emitted with the current :class:`AppSettings`.
        installsDetected: Emitted with the detected installations.
        folderValidated: Emitted with ``(path, ValidationReport)``.
    """

    settingsLoaded = Signal(object)
    installsDetected = Signal(object)
    folderValidated = Signal(str, object)
    dataDirectoryMigrated = Signal(object)

    def __init__(
        self,
        runner: TaskRunner,
        settings: JsonSettingsRepository,
        game: GameService,
        parent: QObject | None = None,
        crash_monitor: CrashMonitorService | None = None,
        data_directories: DataDirectoryService | None = None,
    ) -> None:
        super().__init__(runner, parent)
        self._settings = settings
        self._game = game
        self._crash_monitor = crash_monitor
        self._data_directories = data_directories

    def refresh(self) -> None:
        """Reload the settings from disk."""
        self.settingsLoaded.emit(self._settings.reload())

    def detect_installations(self) -> None:
        """Run auto-detection and publish the candidates."""
        self.statusChanged.emit("Scanning for GTA V installations...")

        def work() -> tuple[GameInstall, ...]:
            return self._game.detect_all()

        def done(installs: tuple[GameInstall, ...]) -> None:
            self.installsDetected.emit(installs)
            self.statusChanged.emit(f"Found {len(installs)} installation(s)")

        self.run(work, done)

    def validate_folder(self, folder: Path) -> None:
        """Validate a manually chosen folder without selecting it."""
        def work() -> ValidationReport:
            return self._game.validate(folder)

        self.run(work, lambda report: self.folderValidated.emit(str(folder), report))

    def select_game(self, folder: Path) -> None:
        """Make ``folder`` the active installation."""
        self.run_result(
            lambda: self._game.select(folder),
            lambda _install: self._after_game_change(folder),
        )

    def update(self, **changes: object) -> None:
        """Persist a partial change to the settings."""
        def work() -> AppSettings:
            updated = replace(self._settings.load(), **changes)  # type: ignore[arg-type]
            self._settings.save(updated)
            return updated

        def done(updated: AppSettings) -> None:
            self.settingsLoaded.emit(updated)
            self.statusChanged.emit("Settings saved")
            self._apply_crash_monitor(updated)

        self.run(work, done)

    def change_data_directory(self, destination: Path) -> None:
        """Copy application data and activate it after restart."""
        if self._data_directories is None:
            self._emit_error("Data-directory migration is unavailable.")
            return
        self.statusChanged.emit("Moving application data...")

        def done(migration: DataDirectoryMigration) -> None:
            self.statusChanged.emit(f"Application data moved to {migration.destination}")
            self.dataDirectoryMigrated.emit(migration)

        self.run(lambda: self._data_directories.migrate(destination), done)

    def _apply_crash_monitor(self, settings: AppSettings) -> None:
        """Start/stop the crash monitor to match the saved preference."""
        if self._crash_monitor is None:
            return
        if settings.crash_monitor_enabled:
            self._crash_monitor.start()
        else:
            self._crash_monitor.stop()

    def _after_game_change(self, folder: Path) -> None:
        """Refresh the page after the active installation changed."""
        self.statusChanged.emit(f"Active installation: {folder}")
        self.refresh()
