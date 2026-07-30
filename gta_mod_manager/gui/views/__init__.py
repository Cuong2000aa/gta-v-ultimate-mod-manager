"""Widgets rendering one page each; all logic lives in the view models."""

from gta_mod_manager.gui.views.backup_view import BackupView
from gta_mod_manager.gui.views.conflict_view import ConflictView
from gta_mod_manager.gui.views.dashboard_view import DashboardView
from gta_mod_manager.gui.views.install_view import InstallView
from gta_mod_manager.gui.views.library_view import LibraryView
from gta_mod_manager.gui.views.log_view import LogView
from gta_mod_manager.gui.views.settings_view import SettingsView

__all__ = [
    "BackupView",
    "ConflictView",
    "DashboardView",
    "InstallView",
    "LibraryView",
    "LogView",
    "SettingsView",
]
