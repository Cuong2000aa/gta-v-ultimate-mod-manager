"""The main window: sidebar, pages, status bar, toasts and drag & drop."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent, QDragEnterEvent, QDropEvent, QResizeEvent
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QProgressBar,
    QStackedWidget,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gta_mod_manager.bootstrap import Application
from gta_mod_manager.core import constants
from gta_mod_manager.core.events import NotificationLevel
from gta_mod_manager.core.progress import EventBusProgressReporter
from gta_mod_manager.gui.event_relay import EventRelay
from gta_mod_manager.gui.i18n import t
from gta_mod_manager.gui.viewmodels.backup_vm import BackupViewModel
from gta_mod_manager.gui.viewmodels.base import ViewModel
from gta_mod_manager.gui.viewmodels.conflict_vm import ConflictViewModel
from gta_mod_manager.gui.viewmodels.dashboard_vm import DashboardViewModel
from gta_mod_manager.gui.viewmodels.diagnostics_vm import DiagnosticsViewModel
from gta_mod_manager.gui.viewmodels.graphics_vm import GraphicsViewModel
from gta_mod_manager.gui.viewmodels.install_vm import InstallViewModel
from gta_mod_manager.gui.viewmodels.library_vm import LibraryViewModel
from gta_mod_manager.gui.viewmodels.log_vm import LogViewModel
from gta_mod_manager.gui.viewmodels.online_vm import OnlineViewModel
from gta_mod_manager.gui.viewmodels.settings_vm import SettingsViewModel
from gta_mod_manager.gui.viewmodels.spawn_vm import SpawnViewModel
from gta_mod_manager.gui.views.backup_view import BackupView
from gta_mod_manager.gui.views.conflict_view import ConflictView
from gta_mod_manager.gui.views.dashboard_view import DashboardView
from gta_mod_manager.gui.views.diagnostics_view import DiagnosticsView
from gta_mod_manager.gui.views.graphics_view import GraphicsView
from gta_mod_manager.gui.views.install_view import InstallView
from gta_mod_manager.gui.views.library_view import LibraryView
from gta_mod_manager.gui.views.log_view import LogView
from gta_mod_manager.gui.views.online_view import OnlineView
from gta_mod_manager.gui.views.settings_view import SettingsView
from gta_mod_manager.gui.views.spawn_view import SpawnView
from gta_mod_manager.gui.widgets.sidebar import Sidebar
from gta_mod_manager.gui.widgets.toast import ToastHost
from gta_mod_manager.gui.workers import TaskRunner
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository
from gta_mod_manager.services.data_directory_service import DataDirectoryService

_TOAST_MARGIN = 24
_WINDOW_MIN_SIZE = (1180, 760)


class MainWindow(QMainWindow):
    """Hosts every page and wires the view models to the application events."""

    def __init__(self, application: Application, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app = application
        self._runner = TaskRunner(self)
        self._relay = EventRelay(application.bus, self)
        self._reporter = application.container.resolve(EventBusProgressReporter)

        self.setWindowTitle(f"{constants.APP_NAME} {constants.APP_VERSION}")
        self.setMinimumSize(*_WINDOW_MIN_SIZE)
        self.setAcceptDrops(True)

        self._build_view_models()
        self._build_layout()
        self._connect_events()

        self._sidebar.select("dashboard")
        self._dashboard.refresh()
        self._settings_view.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_view_models(self) -> None:
        """Create one view model per page."""
        app = self._app
        self._dashboard_vm = DashboardViewModel(
            self._runner,
            app.game,
            app.library,
            app.backups,
            self,
            launch=app.launch,
        )
        self._install_vm = InstallViewModel(
            self._runner,
            app.analysis,
            app.install,
            app.game,
            self._reporter,
            self,
            paths=app.paths,
        )
        self._online_vm = OnlineViewModel(self._runner, app.online, self)
        self._library_vm = LibraryViewModel(
            self._runner, app.library, app.game, self._reporter, self
        )
        self._spawn_vm = SpawnViewModel(
            self._runner, app.spawn_catalog, app.game, self
        )
        self._graphics_vm = GraphicsViewModel(
            self._runner, app.graphics, app.game, self
        )
        self._backup_vm = BackupViewModel(self._runner, app.backups, self._reporter, self)
        self._conflict_vm = ConflictViewModel(self._runner, app.conflicts, app.game, self)
        self._diagnostics_vm = DiagnosticsViewModel(
            self._runner, app.diagnostics, app.game, self
        )
        self._log_vm = LogViewModel(self._runner, app.logging.ring_buffer, self)
        self._settings_vm = SettingsViewModel(
            self._runner,
            app.container.resolve(JsonSettingsRepository),
            app.game,
            self,
            crash_monitor=app.crash_monitor,
            data_directories=app.container.resolve(DataDirectoryService),
        )

    def _build_layout(self) -> None:
        """Assemble the sidebar, the page stack and the status bar."""
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._sidebar = Sidebar()
        self._sidebar.pageSelected.connect(self._show_page)
        layout.addWidget(self._sidebar)

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)
        layout.addWidget(right, 1)

        self._pages = QStackedWidget()
        right_layout.addWidget(self._pages, 1)

        self._dashboard = DashboardView(self._dashboard_vm)
        self._install = InstallView(self._install_vm)
        self._online = OnlineView(self._online_vm)
        self._library = LibraryView(self._library_vm)
        self._spawn = SpawnView(self._spawn_vm)
        self._graphics = GraphicsView(self._graphics_vm)
        self._conflicts = ConflictView(self._conflict_vm)
        self._diagnostics = DiagnosticsView(self._diagnostics_vm)
        self._backups = BackupView(self._backup_vm)
        self._logs = LogView(self._log_vm, self._app.paths.log_file)
        self._settings_view = SettingsView(self._settings_vm, self._app.paths)

        self._page_index: dict[str, int] = {}
        for key, page in (
            ("dashboard", self._dashboard),
            ("install", self._install),
            ("online", self._online),
            ("installed", self._library),
            ("spawn", self._spawn),
            ("graphics", self._graphics),
            ("conflicts", self._conflicts),
            ("diagnostics", self._diagnostics),
            ("backup", self._backups),
            ("logs", self._logs),
            ("settings", self._settings_view),
        ):
            self._page_index[key] = self._pages.addWidget(page)

        self._online.installRequested.connect(self._open_downloaded_mod)

        self._build_status_bar()
        self._toasts = ToastHost(self)
        self._toasts.raise_()

    def _build_status_bar(self) -> None:
        """Create the status bar with the shared progress indicator."""
        status = QStatusBar()
        self.setStatusBar(status)

        self._status_label = QLabel(t("chrome.starting"))
        status.addWidget(self._status_label, 1)

        self._progress = QProgressBar()
        self._progress.setFixedWidth(240)
        self._progress.setVisible(False)
        status.addPermanentWidget(self._progress)

        self._safety_label = QLabel(t("chrome.read_only"))
        self._safety_label.setObjectName("Hint")
        status.addPermanentWidget(self._safety_label)

    def _connect_events(self) -> None:
        """Wire view models and the event relay to the window chrome."""
        for view_model in self._view_models():
            view_model.statusChanged.connect(self._status_label.setText)
            view_model.errorRaised.connect(self._show_error)

        self._runner.busyChanged.connect(self._on_busy)
        self._relay.progress.connect(self._on_progress)
        self._relay.progress.connect(self._library.show_progress)
        self._relay.notified.connect(self._toasts.show_toast)
        self._relay.logged.connect(self._logs.append_live)
        self._relay.gameChanged.connect(self._on_game_changed)
        self._relay.libraryChanged.connect(self._on_library_changed)
        self._relay.sessionStarted.connect(self._on_session_started)
        self._relay.sessionEnded.connect(self._on_session_ended)
        self._install_vm.installFinished.connect(lambda _report: self._after_install())

    def _view_models(self) -> tuple[ViewModel, ...]:
        """Return every view model owned by the window."""
        return (
            self._dashboard_vm,
            self._install_vm,
            self._online_vm,
            self._library_vm,
            self._spawn_vm,
            self._graphics_vm,
            self._backup_vm,
            self._conflict_vm,
            self._diagnostics_vm,
            self._log_vm,
            self._settings_vm,
        )

    # ------------------------------------------------------------------
    # Navigation and events
    # ------------------------------------------------------------------
    def _show_page(self, key: str) -> None:
        """Switch to a page and refresh it lazily."""
        index = self._page_index.get(key)
        if index is None:
            return
        self._pages.setCurrentIndex(index)

        refreshers = {
            "dashboard": self._dashboard.refresh,
            "installed": self._library.refresh,
            "spawn": self._spawn.refresh,
            "graphics": self._graphics.refresh,
            "conflicts": self._conflicts.refresh,
            "diagnostics": self._diagnostics.refresh,
            "backup": self._backups.refresh,
            "logs": self._logs.refresh,
            "settings": self._settings_view.refresh,
        }
        refresh = refreshers.get(key)
        if refresh is not None:
            refresh()

    def _on_busy(self, busy: bool) -> None:
        """Show an indeterminate progress bar while work is running."""
        if busy:
            self._progress.setRange(0, 0)
            self._progress.setVisible(True)
        else:
            self._progress.setVisible(False)
            self._progress.setRange(0, 100)

    def _on_progress(self, _operation: str, label: str, current: int, total: int) -> None:
        """Reflect a progress event in the status bar."""
        self._progress.setVisible(True)
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(current)
        else:
            self._progress.setRange(0, 0)
        if label:
            self._status_label.setText(label)

    def _on_game_changed(self, _game_id: str, root_path: str) -> None:
        """Update the sidebar footer when the active installation changes."""
        self._sidebar.set_footer(t("chrome.game_folder", path=root_path))

    def _on_library_changed(self, _reason: str) -> None:
        """Refresh whichever page is currently visible."""
        current = self._pages.currentWidget()
        if current is self._library:
            self._library.refresh()
        elif current is self._spawn:
            self._spawn.refresh()
        elif current is self._backups:
            self._backups.refresh()
        elif current is self._conflicts:
            self._conflicts.refresh()
        elif current is self._dashboard:
            self._dashboard.refresh()

    def _after_install(self) -> None:
        """Move the user to the library once an installation succeeded."""
        self._sidebar.select("installed")
        self._show_page("installed")

    def _open_downloaded_mod(self, path: object) -> None:
        """Send a freshly downloaded archive to the Install page."""
        candidate = Path(str(path))
        if not candidate.is_file():
            self._show_error(t("online.missing_file", path=candidate))
            return
        self._sidebar.select("install")
        self._show_page("install")
        self._install.load_source(candidate)
        self._toasts.show_toast(
            t("online.ready_toast_title"),
            t("online.ready_toast_body", name=candidate.name),
            NotificationLevel.SUCCESS.value,
        )

    def _on_session_started(self, process_name: str, _pid: int) -> None:
        """Tell the user the crash monitor picked up the game."""
        self._toasts.show_toast(
            t("crash.session_started_title"),
            t("crash.session_started_body", name=process_name),
            NotificationLevel.INFO.value,
        )
        self._status_label.setText(t("crash.session_started_body", name=process_name))

    def _on_session_ended(self, report: object) -> None:
        """Show the outcome of a finished game session."""
        crashed = bool(getattr(report, "crashed", False))
        duration = int(getattr(report, "duration_seconds", 0))
        minutes = max(1, round(duration / 60))
        if crashed:
            suspect = getattr(report, "top_suspect", None)
            detail = (
                suspect.title
                if suspect is not None
                else t("crash.no_suspect")
            )
            self._toasts.show_toast(
                t("crash.detected_title"),
                t("crash.detected_body", minutes=minutes, detail=detail),
                NotificationLevel.ERROR.value,
                duration_ms=15000,
            )
            self._sidebar.select("diagnostics")
            self._show_page("diagnostics")
        else:
            self._toasts.show_toast(
                t("crash.clean_title"),
                t("crash.clean_body", minutes=minutes),
                NotificationLevel.SUCCESS.value,
            )

    def _show_error(self, message: str) -> None:
        """Report an error as a toast so the workflow is never interrupted."""
        self._toasts.show_toast(
            t("chrome.something_wrong"), message, NotificationLevel.ERROR.value, duration_ms=10000
        )
        self._status_label.setText(message.splitlines()[0] if message else t("chrome.error"))

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt override
        """Accept archives dropped anywhere in the window."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt override
        """Route a dropped archive to the install page."""
        for url in event.mimeData().urls():
            if not url.isLocalFile():
                continue
            candidate = Path(url.toLocalFile())
            if not candidate.exists():
                continue
            event.acceptProposedAction()
            self._sidebar.select("install")
            self._show_page("install")
            self._install.load_source(candidate)
            return

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt override
        """Keep the toast host anchored to the bottom-right corner."""
        super().resizeEvent(event)
        width = 380
        height = self.height() - 120
        self._toasts.setGeometry(
            self.width() - width - _TOAST_MARGIN,
            _TOAST_MARGIN,
            width,
            max(120, height),
        )

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt override
        """Release the extraction workspace and detach from the event bus."""
        self._install_vm.clear()
        self._relay.detach()
        self._runner.wait(5000)
        super().closeEvent(event)
