"""Resolution of every directory the application writes to.

Paths are never hardcoded at call sites: components receive an
:class:`AppPaths` instance through dependency injection, which makes tests
able to redirect all I/O into a temporary folder.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.core import constants


@dataclass(frozen=True, slots=True)
class AppPaths:
    """Filesystem layout used by the application at runtime.

    Attributes:
        root: Base folder holding every other working directory.
    """

    root: Path

    @property
    def logs(self) -> Path:
        """Directory for rotating log files."""
        return self.root / constants.DIR_LOGS

    @property
    def temp(self) -> Path:
        """Directory for extraction workspaces; safe to wipe on startup."""
        return self.root / constants.DIR_TEMP

    @property
    def backup(self) -> Path:
        """Directory holding backup snapshots."""
        return self.root / constants.DIR_BACKUP

    @property
    def cache(self) -> Path:
        """Directory for derived data such as thumbnails and hashes."""
        return self.root / constants.DIR_CACHE

    @property
    def config(self) -> Path:
        """Directory holding settings and repository databases."""
        return self.root / constants.DIR_CONFIG

    @property
    def library(self) -> Path:
        """Directory where imported mod archives are kept."""
        return self.root / constants.DIR_LIBRARY

    @property
    def downloads(self) -> Path:
        """Directory for archives fetched from Nexus / GTA5-Mods / direct URLs."""
        return self.root / constants.DIR_DOWNLOADS

    @property
    def settings_file(self) -> Path:
        """Path of the JSON settings document."""
        return self.config / constants.SETTINGS_FILE

    @property
    def mods_db_file(self) -> Path:
        """Path of the installed-mods database."""
        return self.config / constants.MODS_DB_FILE

    @property
    def legacy_mods_db_file(self) -> Path:
        """Path of the JSON mod library used by releases before SQLite."""
        return self.config / constants.LEGACY_MODS_DB_FILE

    @property
    def backup_db_file(self) -> Path:
        """Path of the backup snapshot index."""
        return self.config / constants.BACKUP_DB_FILE

    @property
    def log_file(self) -> Path:
        """Path of the main log file."""
        return self.logs / constants.LOG_FILE

    def all_directories(self) -> tuple[Path, ...]:
        """Return every directory that must exist before the app runs."""
        return (
            self.root,
            self.logs,
            self.temp,
            self.backup,
            self.cache,
            self.config,
            self.library,
            self.downloads,
        )

    def ensure(self) -> "AppPaths":
        """Create all working directories if they do not exist yet."""
        for directory in self.all_directories():
            directory.mkdir(parents=True, exist_ok=True)
        return self

    @classmethod
    def default(cls) -> "AppPaths":
        """Build the standard per-user layout.

        Uses ``%LOCALAPPDATA%`` on Windows and falls back to the platform
        temporary directory when the variable is unavailable.
        """
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("XDG_DATA_HOME")
        root = Path(base) if base else Path(tempfile.gettempdir())
        return cls(root=root / constants.APP_SLUG)

    @classmethod
    def portable(cls, application_dir: Path) -> "AppPaths":
        """Build a portable layout that keeps data next to the executable."""
        return cls(root=application_dir)
