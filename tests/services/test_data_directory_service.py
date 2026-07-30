from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.data_root import (
    configured_data_root,
    finalize_pending_cleanup,
)
from gta_mod_manager.services.data_directory_service import DataDirectoryService


def test_migrate_copies_data_rewrites_paths_and_selects_destination(
    tmp_path: Path,
) -> None:
    source = AppPaths(tmp_path / "old").ensure()
    destination = tmp_path / "new"
    pointer = tmp_path / "bootstrap.json"
    stored = source.backup / "snapshot" / "file.bin"
    stored.parent.mkdir(parents=True)
    stored.write_bytes(b"backup")
    source.backup_db_file.write_text(
        json.dumps(
            {
                "snapshots": {
                    "s1": {
                        "entries": [
                            {
                                "original_path": "D:/Games/GTA5/file.bin",
                                "stored_path": str(stored),
                            }
                        ]
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    _create_mod_database(source.mods_db_file, source.cache / "preview.png")

    migration = DataDirectoryService(
        source, bootstrap_file=pointer
    ).migrate(destination)

    assert migration.destination == destination.resolve()
    assert (destination / "backup/snapshot/file.bin").read_bytes() == b"backup"
    payload = json.loads(
        (destination / "config/backups.json").read_text(encoding="utf-8")
    )
    rewritten = payload["snapshots"]["s1"]["entries"][0]["stored_path"]
    assert rewritten == str(destination / "backup/snapshot/file.bin")
    assert configured_data_root(pointer) == destination.resolve()
    with sqlite3.connect(destination / "config/installed_mods.sqlite3") as connection:
        mod_payload = json.loads(
            connection.execute("SELECT payload FROM mods").fetchone()[0]
        )
    assert mod_payload["preview_image"] == str(destination / "cache/preview.png")
    assert source.root.exists()  # Removed only after a successful fresh launch.


def test_finalize_cleanup_deletes_old_copy_only_after_marker(tmp_path: Path) -> None:
    source = AppPaths(tmp_path / "old").ensure()
    destination = tmp_path / "new"
    pointer = tmp_path / "bootstrap.json"
    DataDirectoryService(source, bootstrap_file=pointer).migrate(destination)

    assert finalize_pending_cleanup(destination, pointer)
    assert not source.root.exists()
    assert destination.exists()
    assert not (destination / constants.DATA_MIGRATION_MARKER_FILE).exists()


def test_migration_rejects_non_empty_destination(tmp_path: Path) -> None:
    source = AppPaths(tmp_path / "old").ensure()
    destination = tmp_path / "occupied"
    destination.mkdir()
    (destination / "other.txt").write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError, match="empty folder"):
        DataDirectoryService(
            source, bootstrap_file=tmp_path / "bootstrap.json"
        ).migrate(destination)

    assert (destination / "other.txt").read_text(encoding="utf-8") == "keep"


def _create_mod_database(path: Path, preview: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            "CREATE TABLE mods (mod_id TEXT PRIMARY KEY, payload TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO mods (mod_id, payload) VALUES (?, ?)",
            ("m1", json.dumps({"mod_id": "m1", "preview_image": str(preview)})),
        )
