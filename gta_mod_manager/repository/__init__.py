"""Persistence adapters implementing the repository ports."""

from gta_mod_manager.repository.backup_repository import JsonBackupRepository
from gta_mod_manager.repository.json_store import JsonStore
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.repository.sqlite_mod_repository import SqliteModRepository
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository

__all__ = [
    "JsonBackupRepository",
    "JsonModRepository",
    "SqliteModRepository",
    "JsonSettingsRepository",
    "JsonStore",
]
