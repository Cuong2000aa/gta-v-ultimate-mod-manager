"""Safe two-phase migration of the application's data directory."""

from __future__ import annotations

import json
import shutil
import sqlite3
import uuid
from dataclasses import dataclass
from pathlib import Path

from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.data_root import pointer_file, write_data_root


@dataclass(frozen=True, slots=True)
class DataDirectoryMigration:
    """A completed copy that becomes active after restarting."""

    previous_root: Path
    destination: Path


class DataDirectoryService:
    """Copies app data and records the destination for the next launch."""

    def __init__(self, paths: AppPaths, *, bootstrap_file: Path | None = None) -> None:
        self._paths = paths
        self._bootstrap_file = bootstrap_file or pointer_file()

    def migrate(self, destination: Path) -> DataDirectoryMigration:
        """Copy current data to an empty folder and switch on next launch."""
        source = self._paths.root.resolve()
        target = destination.expanduser().resolve()
        self._validate_destination(source, target)

        if source == target:
            write_data_root(target, path=self._bootstrap_file)
            return DataDirectoryMigration(source, target)

        target.parent.mkdir(parents=True, exist_ok=True)
        staging = target.with_name(f".{target.name}.migrating-{uuid.uuid4().hex[:8]}")
        try:
            shutil.copytree(source, staging, ignore=self._ignore_transient)
            self._rewrite_moved_paths(staging, source, target)
            (staging / constants.DATA_MIGRATION_MARKER_FILE).write_text(
                str(source), encoding="utf-8"
            )
            if target.exists():
                target.rmdir()  # Validation permits an empty existing directory.
            # os.replace() cannot rename directories reliably on Windows.
            shutil.move(str(staging), str(target))
            write_data_root(
                target,
                previous_root=source,
                path=self._bootstrap_file,
            )
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            raise
        return DataDirectoryMigration(source, target)

    @staticmethod
    def _validate_destination(source: Path, target: Path) -> None:
        if source == target:
            return
        if _contains(source, target) or _contains(target, source):
            raise ValueError(
                "The new data folder cannot be inside the current folder (or contain it)."
            )
        if target.exists():
            if not target.is_dir():
                raise ValueError("The selected destination is not a folder.")
            if any(target.iterdir()):
                raise ValueError("Select a new or empty folder for application data.")

    @staticmethod
    def _ignore_transient(_folder: str, names: list[str]) -> set[str]:
        ignored = {constants.DATA_MIGRATION_MARKER_FILE}
        # Extraction workspaces are disposable and may be changing while copied.
        if Path(_folder).name == constants.DIR_TEMP:
            ignored.update(names)
        return ignored

    @classmethod
    def _rewrite_moved_paths(cls, copied_root: Path, old: Path, new: Path) -> None:
        config = copied_root / constants.DIR_CONFIG
        for filename in (
            constants.BACKUP_DB_FILE,
            constants.LEGACY_MODS_DB_FILE,
            constants.SETTINGS_FILE,
        ):
            cls._rewrite_json_file(config / filename, old, new)
        cls._rewrite_sqlite_payloads(config / constants.MODS_DB_FILE, old, new)

    @classmethod
    def _rewrite_json_file(cls, path: Path, old: Path, new: Path) -> None:
        if not path.is_file():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        rewritten = cls._rewrite_value(payload, old, new)
        path.write_text(
            json.dumps(rewritten, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def _rewrite_sqlite_payloads(cls, path: Path, old: Path, new: Path) -> None:
        if not path.is_file():
            return
        connection = sqlite3.connect(path)
        try:
            rows = connection.execute("SELECT mod_id, payload FROM mods").fetchall()
            updates: list[tuple[str, str]] = []
            for mod_id, raw_payload in rows:
                try:
                    payload = json.loads(raw_payload)
                except (TypeError, json.JSONDecodeError):
                    continue
                rewritten = cls._rewrite_value(payload, old, new)
                if rewritten != payload:
                    updates.append(
                        (json.dumps(rewritten, ensure_ascii=False), str(mod_id))
                    )
            connection.executemany(
                "UPDATE mods SET payload = ? WHERE mod_id = ?", updates
            )
            connection.commit()
        finally:
            connection.close()

    @classmethod
    def _rewrite_value(cls, value: object, old: Path, new: Path) -> object:
        if isinstance(value, dict):
            return {
                key: cls._rewrite_value(item, old, new)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [cls._rewrite_value(item, old, new) for item in value]
        if not isinstance(value, str):
            return value
        candidate = Path(value)
        if not candidate.is_absolute():
            return value
        try:
            relative = candidate.relative_to(old)
        except ValueError:
            return value
        return str(new / relative)


def _contains(parent: Path, child: Path) -> bool:
    try:
        child.relative_to(parent)
    except ValueError:
        return False
    return True
