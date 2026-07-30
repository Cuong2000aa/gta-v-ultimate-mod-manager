"""Tests for the Conflict Center audit of installed mods."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.models.enums import ConflictSeverity, ConflictType, GamePlatform, ModKind
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod
from gta_mod_manager.repository.mod_repository import JsonModRepository
from gta_mod_manager.services.conflict_service import ConflictService


def _mod(
    game_root: Path,
    *,
    mod_id: str,
    name: str,
    spawn_codes: tuple[str, ...] = (),
    files: tuple[InstalledFileRecord, ...] = (),
) -> InstalledMod:
    return InstalledMod(
        mod_id=mod_id,
        display_name=name,
        game_root=game_root,
        kind=ModKind.VEHICLE_REPLACE.value,
        installed_files=files,
        spawn_codes=spawn_codes,
    )


def test_shared_x64e_alone_is_not_a_conflict(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    archive = game_root / "mods" / "x64e.rpf"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"rpf")

    repo = JsonModRepository.at(tmp_path / "installed_mods.json")
    for mod_id, name, members in (
        ("a", "Ferrari", ("levels/gta5/vehicles.rpf/buffalo2.yft",)),
        ("b", "Dodge", ("levels/gta5/vehicles.rpf/gauntlet.yft",)),
    ):
        repo.add(
            _mod(
                game_root,
                mod_id=mod_id,
                name=name,
                files=(
                    InstalledFileRecord(
                        target_path=archive,
                        shared_archive=True,
                        archive_members=members,
                    ),
                ),
            )
        )

    report = ConflictService(repo).audit(
        GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.STEAM)
    )

    assert report.conflicts == ()


def test_two_mods_replacing_same_spawn_are_blocking(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    archive = game_root / "mods" / "x64e.rpf"
    archive.parent.mkdir(parents=True)
    archive.write_bytes(b"rpf")

    repo = JsonModRepository.at(tmp_path / "installed_mods.json")
    repo.add(
        _mod(
            game_root,
            mod_id="a",
            name="Portofino",
            spawn_codes=("buffalo2",),
            files=(
                InstalledFileRecord(
                    target_path=archive,
                    shared_archive=True,
                    archive_members=("levels/gta5/vehicles.rpf/buffalo2.yft",),
                ),
            ),
        )
    )
    repo.add(
        _mod(
            game_root,
            mod_id="b",
            name="Other Buffalo",
            files=(
                InstalledFileRecord(
                    target_path=archive,
                    shared_archive=True,
                    archive_members=(
                        "levels/gta5/vehicles.rpf/buffalo2.ytd",
                        "levels/gta5/vehicles.rpf/buffalo2_hi.yft",
                    ),
                ),
            ),
        )
    )

    report = ConflictService(repo).audit(
        GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.STEAM)
    )

    assert len(report.conflicts) == 1
    conflict = report.conflicts[0]
    assert conflict.conflict_type is ConflictType.DUPLICATE_VEHICLE_NAME
    assert conflict.severity is ConflictSeverity.BLOCKING
    assert conflict.key == "buffalo2"
    assert "Portofino" in conflict.description
    assert "Other Buffalo" in conflict.description
