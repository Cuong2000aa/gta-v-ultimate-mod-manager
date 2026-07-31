"""Tests for physical enable/disable of library mods."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.events import EventBus
from gta_mod_manager.installer.uninstaller import Uninstaller
from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod
from gta_mod_manager.repository.backup_repository import JsonBackupRepository
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.services.backup_service import BackupService
from gta_mod_manager.services.library_service import LibraryService


def _service(tmp_path: Path) -> tuple[LibraryService, Path, JsonModRepository]:
    game_root = tmp_path / "game"
    game_root.mkdir()
    paths = AppPaths(tmp_path / "app").ensure()
    mods = JsonModRepository.at(paths.config / "mods.json")
    from gta_mod_manager.backup.backup_engine import BackupEngine
    from gta_mod_manager.backup.snapshot_store import SnapshotStore

    bus = EventBus()
    backup_repo = JsonBackupRepository.at(paths.backup_db_file)
    engine = BackupEngine(store=SnapshotStore(paths), repository=backup_repo)
    backups = BackupService(engine=engine, repository=backup_repo, bus=bus)
    library = LibraryService(
        mods=mods,
        uninstaller=Uninstaller(),
        backups=backups,
        backup_repository=backup_repo,
        bus=bus,
        paths=paths,
    )
    return library, game_root, mods


def test_physical_disable_and_enable_moves_loose_files(tmp_path: Path) -> None:
    library, game_root, mods = _service(tmp_path)
    scripts = game_root / "scripts"
    scripts.mkdir()
    script = scripts / "CoolScript.dll"
    script.write_bytes(b"payload-bytes")

    mod = InstalledMod(
        mod_id="cool-script",
        display_name="Cool Script",
        game_root=game_root,
        kind="script",
        installed_files=(InstalledFileRecord(target_path=script),),
    )
    mods.add(mod)

    disabled = library.set_enabled("cool-script", False).unwrap()
    assert disabled.status is ModStatus.DISABLED
    assert not script.exists()
    quarantine = (
        library._paths.backup / "disabled-mods" / "cool-script" / "scripts" / "CoolScript.dll"
    )
    assert quarantine.is_file()
    assert quarantine.read_bytes() == b"payload-bytes"

    verify = library.verify("cool-script").unwrap()
    assert verify == ()
    assert mods.get("cool-script").status is ModStatus.DISABLED

    enabled = library.set_enabled("cool-script", True).unwrap()
    assert enabled.status is ModStatus.INSTALLED
    assert script.is_file()
    assert script.read_bytes() == b"payload-bytes"
    assert not quarantine.exists()


def test_verify_keeps_disabled_status(tmp_path: Path) -> None:
    library, game_root, mods = _service(tmp_path)
    target = game_root / "scripts" / "A.dll"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"a")
    mods.add(
        InstalledMod(
            mod_id="a",
            display_name="A",
            game_root=game_root,
            kind="script",
            installed_files=(InstalledFileRecord(target_path=target),),
        )
    )
    library.set_enabled("a", False).unwrap()
    library.verify("a").unwrap()
    assert mods.get("a").status is ModStatus.DISABLED


def test_list_installed_tolerates_openiv_staging_paths(tmp_path: Path) -> None:
    library, game_root, mods = _service(tmp_path)
    staging = tmp_path / "app" / "library" / "openiv-payload" / "wheel.ydr"
    staging.parent.mkdir(parents=True)
    staging.write_bytes(b"mesh")
    mods.add(
        InstalledMod(
            mod_id="staged-wheel",
            display_name="Staged Wheel",
            game_root=game_root,
            kind="vehicle",
            installed_files=(InstalledFileRecord(target_path=staging),),
        )
    )

    summaries = library.list_installed()
    assert len(summaries) == 1
    assert summaries[0].display_name == "Staged Wheel"
    assert summaries[0].is_intact
