"""Tests for JSON persistence: atomic writes, codecs and queries."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.models.backup_snapshot import BackupEntry, BackupSnapshot, OperationRecord
from gta_mod_manager.models.enums import ModStatus, OperationKind, OperationStatus
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod
from gta_mod_manager.repository.backup_repository import JsonBackupRepository
from gta_mod_manager.repository.json_store import JsonStore
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.repository.sqlite_mod_repository import SqliteModRepository
from gta_mod_manager.models.vehicle import VehicleDefinition
from gta_mod_manager.repository.settings_repository import JsonSettingsRepository


def _mod(mod_id: str, game_root: Path, *, name: str = "Test Mod") -> InstalledMod:
    """Return an installed-mod record for ``game_root``."""
    return InstalledMod(
        mod_id=mod_id,
        display_name=name,
        game_root=game_root,
        kind="vehicle_addon",
        installed_files=(
            InstalledFileRecord(
                target_path=game_root / "mods" / f"{mod_id}.rpf",
                sha256="abc",
                replaced_existing=False,
            ),
        ),
        spawn_codes=("adder2",),
        dlc_packs=("adder2",),
    )


def test_a_missing_document_returns_the_default(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "db.json", default={"version": 1, "mods": {}})

    assert store.read() == {"version": 1, "mods": {}}
    assert not store.exists()


def test_a_corrupted_document_is_quarantined(tmp_path: Path) -> None:
    path = tmp_path / "db.json"
    path.write_text("{not valid json", encoding="utf-8")
    store = JsonStore(path, default={"version": 1})

    assert store.read() == {"version": 1}
    assert list(tmp_path.glob("db.json.corrupt*"))


def test_writes_leave_no_temporary_file_behind(tmp_path: Path) -> None:
    store = JsonStore(tmp_path / "db.json")

    store.write({"a": 1})

    assert store.read() == {"a": 1}
    assert not list(tmp_path.glob("*.tmp"))


def test_mods_round_trip_through_the_repository(
    app_paths: AppPaths, game_root: Path
) -> None:
    repository = JsonModRepository.at(app_paths.mods_db_file)
    repository.add(_mod("mod-1", game_root))

    loaded = repository.get("mod-1")

    assert loaded is not None
    assert loaded.display_name == "Test Mod"
    assert loaded.game_root == game_root
    assert loaded.installed_files[0].sha256 == "abc"
    assert loaded.spawn_codes == ("adder2",)


def test_mods_are_filtered_by_installation(
    app_paths: AppPaths, game_root: Path, tmp_path: Path
) -> None:
    other_root = tmp_path / "Other GTA V"
    other_root.mkdir()
    repository = JsonModRepository.at(app_paths.mods_db_file)
    repository.add(_mod("mine", game_root))
    repository.add(_mod("theirs", other_root))

    assert [item.mod_id for item in repository.list_for_game(game_root)] == ["mine"]


def test_the_owner_of_a_file_can_be_looked_up(
    app_paths: AppPaths, game_root: Path
) -> None:
    repository = JsonModRepository.at(app_paths.mods_db_file)
    repository.add(_mod("mod-1", game_root))

    owner = repository.find_owner_of(game_root / "mods" / "mod-1.rpf")

    assert owner is not None
    assert owner.mod_id == "mod-1"
    assert repository.find_owner_of(game_root / "mods" / "unknown.rpf") is None


def test_status_updates_are_persisted(app_paths: AppPaths, game_root: Path) -> None:
    repository = JsonModRepository.at(app_paths.mods_db_file)
    repository.add(_mod("mod-1", game_root))

    repository.update_status("mod-1", ModStatus.DISABLED)

    assert repository.get("mod-1").status is ModStatus.DISABLED  # type: ignore[union-attr]
    assert repository.list_active() == ()
    assert repository.update_status("unknown", ModStatus.BROKEN) is None


def test_sqlite_mods_round_trip_and_index_file_owners(
    app_paths: AppPaths, game_root: Path
) -> None:
    repository = SqliteModRepository.at(app_paths.mods_db_file)
    repository.add(_mod("mod-1", game_root))

    loaded = repository.get("mod-1")
    owner = repository.find_owner_of(game_root / "mods" / "mod-1.rpf")

    assert loaded is not None
    assert loaded.spawn_codes == ("adder2",)
    assert owner is not None
    assert owner.mod_id == "mod-1"


def test_sqlite_migrates_the_legacy_json_library(
    app_paths: AppPaths, game_root: Path
) -> None:
    JsonModRepository.at(app_paths.legacy_mods_db_file).add(_mod("legacy", game_root))

    repository = SqliteModRepository.at(
        app_paths.mods_db_file, legacy_json_path=app_paths.legacy_mods_db_file
    )

    assert repository.get("legacy") is not None
    assert app_paths.legacy_mods_db_file.exists()


def test_sqlite_preserves_vehicle_explorer_metadata(
    app_paths: AppPaths, game_root: Path
) -> None:
    repository = SqliteModRepository.at(app_paths.mods_db_file)
    mod = _mod("m4", game_root)
    repository.add(
        replace(
            mod,
            vehicle_definitions=(
                VehicleDefinition(
                    model_name="m4g82",
                    handling_id="M4G82",
                    manufacturer="BMW",
                    vehicle_class="VC_SPORT",
                ),
            ),
        )
    )

    loaded = repository.get("m4")

    assert loaded is not None
    assert loaded.vehicle_definitions[0].spawn_code == "m4g82"
    assert loaded.vehicle_definitions[0].handling_id == "M4G82"


def test_snapshots_are_listed_newest_first(app_paths: AppPaths, game_root: Path) -> None:
    repository = JsonBackupRepository.at(app_paths.backup_db_file)
    older = BackupSnapshot(
        snapshot_id="old",
        game_root=game_root,
        reason="older",
        created_at=datetime(2024, 1, 1, tzinfo=timezone.utc),
        entries=(BackupEntry(original_path=game_root / "a.ini", stored_path=None, existed=False),),
    )
    newer = BackupSnapshot(
        snapshot_id="new",
        game_root=game_root,
        reason="newer",
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    repository.add_snapshot(older)
    repository.add_snapshot(newer)

    assert [item.snapshot_id for item in repository.list_snapshots()] == ["new", "old"]
    assert repository.get_snapshot("old") is not None
    assert repository.get_snapshot("missing") is None


def test_operations_form_an_audit_trail(app_paths: AppPaths) -> None:
    repository = JsonBackupRepository.at(app_paths.backup_db_file)
    record = OperationRecord(
        operation_id="op-1",
        kind=OperationKind.INSTALL,
        status=OperationStatus.RUNNING,
        description="Install Test Mod",
    )
    repository.add_operation(record)
    repository.add_operation(record.completed(OperationStatus.SUCCEEDED))

    operations = repository.list_operations()

    assert len(operations) == 1
    assert operations[0].status is OperationStatus.SUCCEEDED
    assert operations[0].finished_at is not None


def test_settings_round_trip_and_cache_invalidation(
    app_paths: AppPaths, game_root: Path
) -> None:
    repository = JsonSettingsRepository.at(app_paths.settings_file)
    defaults = repository.load()

    assert defaults.auto_backup
    assert defaults.game_root is None

    repository.save(defaults.with_game_root(game_root))

    assert repository.load().game_root == game_root
    assert JsonSettingsRepository.at(app_paths.settings_file).load().game_root == game_root
    assert repository.reload().game_root == game_root
