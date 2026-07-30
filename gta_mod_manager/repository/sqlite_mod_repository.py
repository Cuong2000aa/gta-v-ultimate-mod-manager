"""SQLite-backed library for installed GTA V mods.

The database keeps the full manifest as JSON for forward compatibility and a
separate file index for fast ownership/conflict lookups.  Existing JSON
libraries are imported once, without deleting the source document.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from gta_mod_manager.core.logging_setup import get_logger
from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.models.mod_package import InstalledMod
from gta_mod_manager.repository import codecs
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.utils import fs

_LOGGER = get_logger("repository.sqlite_mods")
_SCHEMA_VERSION = 1


class SqliteModRepository:
    """Stores mod manifests and their owned files in an SQLite database."""

    def __init__(self, path: Path, legacy_json_path: Path | None = None) -> None:
        self._path = path
        self._legacy_json_path = legacy_json_path
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._initialise()

    @classmethod
    def at(
        cls, path: Path, *, legacy_json_path: Path | None = None
    ) -> "SqliteModRepository":
        """Open ``path`` and migrate the legacy JSON library when needed."""
        return cls(path, legacy_json_path)

    def add(self, mod: InstalledMod) -> None:
        """Insert or replace ``mod`` and its complete file manifest."""
        payload = json.dumps(codecs.encode_installed_mod(mod), ensure_ascii=False)
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO mods (mod_id, game_root, status, installed_at, payload)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(mod_id) DO UPDATE SET
                    game_root=excluded.game_root,
                    status=excluded.status,
                    installed_at=excluded.installed_at,
                    payload=excluded.payload
                """,
                (
                    mod.mod_id,
                    str(fs.normalise(mod.game_root)),
                    mod.status.value,
                    mod.installed_at.isoformat(),
                    payload,
                ),
            )
            connection.execute("DELETE FROM mod_files WHERE mod_id = ?", (mod.mod_id,))
            connection.executemany(
                "INSERT INTO mod_files (mod_id, target_path) VALUES (?, ?)",
                [
                    (mod.mod_id, str(fs.normalise(record.target_path)))
                    for record in mod.installed_files
                ],
            )
        _LOGGER.info("Registered installed mod %s (%s)", mod.display_name, mod.mod_id)

    def remove(self, mod_id: str) -> None:
        """Delete a mod and its file index if it exists."""
        with self._connect() as connection:
            connection.execute("DELETE FROM mods WHERE mod_id = ?", (mod_id,))
        _LOGGER.info("Removed installed mod record %s", mod_id)

    def get(self, mod_id: str) -> InstalledMod | None:
        """Return the tracked manifest for ``mod_id`` if present."""
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM mods WHERE mod_id = ?", (mod_id,)
            ).fetchone()
        return self._decode(row["payload"]) if row else None

    def list_all(self) -> tuple[InstalledMod, ...]:
        """Return every tracked mod, newest installation first."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM mods ORDER BY installed_at DESC"
            ).fetchall()
        return tuple(self._decode(row["payload"]) for row in rows)

    def list_for_game(self, game_root: Path) -> tuple[InstalledMod, ...]:
        """Return the mods installed into ``game_root``."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM mods WHERE game_root = ? ORDER BY installed_at DESC",
                (str(fs.normalise(game_root)),),
            ).fetchall()
        return tuple(self._decode(row["payload"]) for row in rows)

    def list_active(self) -> tuple[InstalledMod, ...]:
        """Return enabled installed mods."""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM mods WHERE status = ? ORDER BY installed_at DESC",
                (ModStatus.INSTALLED.value,),
            ).fetchall()
        return tuple(self._decode(row["payload"]) for row in rows)

    def find_owner_of(self, target_path: Path) -> InstalledMod | None:
        """Return the mod owning ``target_path``, if the library tracks one."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT mods.payload FROM mod_files
                JOIN mods ON mods.mod_id = mod_files.mod_id
                WHERE mod_files.target_path = ?
                ORDER BY mods.installed_at DESC LIMIT 1
                """,
                (str(fs.normalise(target_path)),),
            ).fetchone()
        return self._decode(row["payload"]) if row else None

    def update_status(self, mod_id: str, status: ModStatus) -> InstalledMod | None:
        """Change a mod status and return its updated manifest."""
        existing = self.get(mod_id)
        if existing is None:
            return None
        updated = existing.with_status(status)
        self.add(updated)
        return updated

    def _initialise(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS metadata (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS mods (
                    mod_id TEXT PRIMARY KEY,
                    game_root TEXT NOT NULL,
                    status TEXT NOT NULL,
                    installed_at TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_mods_game_root ON mods(game_root);
                CREATE INDEX IF NOT EXISTS idx_mods_status ON mods(status);
                CREATE TABLE IF NOT EXISTS mod_files (
                    mod_id TEXT NOT NULL REFERENCES mods(mod_id) ON DELETE CASCADE,
                    target_path TEXT NOT NULL,
                    PRIMARY KEY (mod_id, target_path)
                );
                CREATE INDEX IF NOT EXISTS idx_mod_files_target ON mod_files(target_path);
                """
            )
            connection.execute(
                "INSERT OR IGNORE INTO metadata (key, value) VALUES ('schema_version', ?)",
                (str(_SCHEMA_VERSION),),
            )
        self._migrate_json_once()

    def _migrate_json_once(self) -> None:
        """Import the former JSON library exactly once, retaining its file."""
        if self._legacy_json_path is None or not self._legacy_json_path.is_file():
            return
        with self._connect() as connection:
            migrated = connection.execute(
                "SELECT value FROM metadata WHERE key = 'legacy_json_migrated'"
            ).fetchone()
        if migrated:
            return
        legacy = JsonModRepository.at(self._legacy_json_path)
        records = legacy.list_all()
        for record in records:
            self.add(record)
        with self._connect() as connection:
            connection.execute(
                "INSERT OR REPLACE INTO metadata (key, value) VALUES ('legacy_json_migrated', ?)",
                (str(len(records)),),
            )
        _LOGGER.info("Migrated %d installed-mod record(s) from JSON to SQLite", len(records))

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _decode(payload: str) -> InstalledMod:
        return codecs.decode_installed_mod(json.loads(payload))
