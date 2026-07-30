"""Tests for the conflict rules and the detector that aggregates them."""

from __future__ import annotations

from pathlib import Path

import pytest

from gta_mod_manager.installer.conflict_detector import ConflictDetector
from gta_mod_manager.installer.conflict_rules import (
    ConflictContext,
    ConflictRule,
    DuplicateDlcRule,
    DuplicateGameConfigRule,
    DuplicateHandlingRule,
    DuplicatePackfileRule,
    DuplicateTextureRule,
    DuplicateVehicleRule,
    FileOverwriteRule,
    MissingDependencyRule,
    ProtectedTargetRule,
)
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.enums import (
    ConflictSeverity,
    ConflictType,
    FileAction,
    GamePlatform,
    InstallTarget,
    ModKind,
)
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import ArchiveMemberImport, FileOperation, InstallPlan
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.mod_package import (
    InstalledFileRecord,
    InstalledMod,
    ModPackage,
)
from gta_mod_manager.models.vehicle import (
    DlcPackDefinition,
    HandlingDefinition,
    VehicleDefinition,
    VehicleManifest,
)


@pytest.fixture()
def install(game_root: Path) -> GameInstall:
    """Return an installation pointing at the fake game folder."""
    return GameInstall(
        game_id="gta_v", root_path=game_root, platform=GamePlatform.STEAM
    )


def _plan(
    game_root: Path,
    *operations: FileOperation,
    package_id: str = "pkg-1",
    dependency_warnings: tuple[str, ...] = (),
) -> InstallPlan:
    """Return a plan carrying ``operations``."""
    return InstallPlan(
        plan_id="plan-1",
        package_id=package_id,
        display_name="Test Mod",
        game_root=game_root,
        operations=operations,
        dependency_warnings=dependency_warnings,
    )


def _operation(
    target: Path,
    action: FileAction = FileAction.COPY,
    kind: InstallTarget = InstallTarget.MODS_FOLDER,
) -> FileOperation:
    """Return a single file operation."""
    return FileOperation(
        action=action, target_path=target, source_path=None, target_kind=kind
    )


def _package(
    tmp_path: Path,
    *,
    vehicles: VehicleManifest | None = None,
    files: tuple[ModFile, ...] = (),
    package_id: str = "pkg-1",
) -> ModPackage:
    """Return a minimal analysed package."""
    return ModPackage(
        package_id=package_id,
        display_name="Test Mod",
        source_path=tmp_path / "mod.zip",
        extracted_root=tmp_path / "extracted",
        inventory=FileInventory(root=tmp_path / "extracted", files=files),
        classification=ModClassification.unknown(),
        vehicles=vehicles or VehicleManifest(),
    )


def _mod_file(root: Path, relative: str) -> ModFile:
    """Return a package file entry rooted at ``root``."""
    return ModFile(
        absolute_path=root / relative,
        relative_path=Path(relative),
        size_bytes=1,
    )


def _installed(
    game_root: Path,
    *,
    mod_id: str,
    name: str,
    files: tuple[Path, ...] = (),
    spawn_codes: tuple[str, ...] = (),
    dlc_packs: tuple[str, ...] = (),
    installed_files: tuple[InstalledFileRecord, ...] | None = None,
) -> InstalledMod:
    """Return a tracked mod owning ``files``."""
    records = installed_files or tuple(
        InstalledFileRecord(target_path=path) for path in files
    )
    return InstalledMod(
        mod_id=mod_id,
        display_name=name,
        game_root=game_root,
        kind=ModKind.UNKNOWN.value,
        installed_files=records,
        spawn_codes=spawn_codes,
        dlc_packs=dlc_packs,
    )


def test_a_protected_root_file_is_blocking(
    install: GameInstall, game_root: Path
) -> None:
    plan = _plan(game_root, _operation(game_root / "GTA5.exe", kind=InstallTarget.GAME_ROOT))

    conflicts = tuple(
        ProtectedTargetRule().evaluate(ConflictContext(plan=plan, install=install))
    )

    assert conflicts[0].severity is ConflictSeverity.BLOCKING
    assert conflicts[0].conflict_type is ConflictType.PROTECTED_TARGET


def test_the_same_name_inside_the_mods_folder_is_allowed(
    install: GameInstall, game_root: Path
) -> None:
    plan = _plan(game_root, _operation(install.mods_path / "update" / "update.rpf"))

    assert not tuple(
        ProtectedTargetRule().evaluate(ConflictContext(plan=plan, install=install))
    )


def test_an_overwrite_names_the_owning_mod(
    install: GameInstall, game_root: Path
) -> None:
    target = install.mods_path / "update" / "x64" / "dlcpacks" / "p" / "dlc.rpf"
    plan = _plan(game_root, _operation(target, action=FileAction.OVERWRITE))
    owner = _installed(game_root, mod_id="other", name="Other Mod", files=(target,))

    conflicts = tuple(
        FileOverwriteRule().evaluate(
            ConflictContext(plan=plan, install=install, installed=(owner,))
        )
    )

    assert conflicts[0].owner == "Other Mod"
    assert conflicts[0].severity is ConflictSeverity.WARNING


def test_a_spawn_code_owned_by_another_mod_is_blocking(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    package = _package(
        tmp_path,
        vehicles=VehicleManifest(vehicles=(VehicleDefinition(model_name="adder2"),)),
    )
    other = _installed(
        game_root, mod_id="other", name="Other Mod", spawn_codes=("adder2",)
    )
    plan = _plan(game_root, _operation(install.mods_path / "a.rpf"))

    conflicts = tuple(
        DuplicateVehicleRule().evaluate(
            ConflictContext(
                plan=plan, install=install, package=package, installed=(other,)
            )
        )
    )

    assert conflicts[0].key == "adder2"
    assert conflicts[0].severity is ConflictSeverity.BLOCKING


def test_reinstalling_the_same_mod_is_not_a_spawn_code_conflict(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    package = _package(
        tmp_path,
        vehicles=VehicleManifest(vehicles=(VehicleDefinition(model_name="adder2"),)),
    )
    same = _installed(
        game_root, mod_id="pkg-1", name="Test Mod", spawn_codes=("adder2",)
    )
    plan = _plan(game_root, _operation(install.mods_path / "a.rpf"))

    assert not tuple(
        DuplicateVehicleRule().evaluate(
            ConflictContext(
                plan=plan, install=install, package=package, installed=(same,)
            )
        )
    )


def test_a_handling_id_declared_twice_is_reported(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    package = _package(
        tmp_path,
        vehicles=VehicleManifest(
            handling=(
                HandlingDefinition(handling_id="ADDER2"),
                HandlingDefinition(handling_id="ADDER2"),
                HandlingDefinition(handling_id="ZENTORNO"),
            )
        ),
    )
    plan = _plan(game_root, _operation(install.mods_path / "a.rpf"))

    conflicts = tuple(
        DuplicateHandlingRule().evaluate(
            ConflictContext(plan=plan, install=install, package=package)
        )
    )

    assert [conflict.key for conflict in conflicts] == ["ADDER2"]
    assert conflicts[0].severity is ConflictSeverity.WARNING


def test_a_dlc_pack_already_on_disk_is_blocking(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    (install.dlc_packs_path / "adder2").mkdir(parents=True)
    package = _package(
        tmp_path, vehicles=VehicleManifest(dlc_packs=(DlcPackDefinition(pack_name="adder2"),))
    )
    plan = _plan(game_root, _operation(install.mods_path / "a.rpf"))

    conflicts = tuple(
        DuplicateDlcRule().evaluate(
            ConflictContext(plan=plan, install=install, package=package)
        )
    )

    assert conflicts[0].conflict_type is ConflictType.DUPLICATE_DLC
    assert conflicts[0].severity is ConflictSeverity.BLOCKING


def test_reinstalling_over_its_own_dlc_pack_is_allowed(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    pack_dir = install.dlc_packs_path / "adder2"
    pack_dir.mkdir(parents=True)
    (pack_dir / "dlc.rpf").write_bytes(b"payload")
    package = _package(
        tmp_path, vehicles=VehicleManifest(dlc_packs=(DlcPackDefinition(pack_name="adder2"),))
    )
    plan = _plan(game_root, _operation(install.mods_path / "a.rpf"))
    same = _installed(
        game_root, mod_id="pkg-1", name="Test Mod", files=(pack_dir / "dlc.rpf",)
    )

    assert not tuple(
        DuplicateDlcRule().evaluate(
            ConflictContext(
                plan=plan, install=install, package=package, installed=(same,)
            )
        )
    )


def test_a_second_gameconfig_mod_is_blocking(
    install: GameInstall, game_root: Path
) -> None:
    target = install.mods_path / "update" / "gameconfig.xml"
    plan = _plan(game_root, _operation(target))
    other = _installed(
        game_root,
        mod_id="other",
        name="Gameconfig Fix",
        files=(install.mods_path / "elsewhere" / "gameconfig.xml",),
    )

    conflicts = tuple(
        DuplicateGameConfigRule().evaluate(
            ConflictContext(plan=plan, install=install, installed=(other,))
        )
    )

    assert conflicts[0].conflict_type is ConflictType.DUPLICATE_GAMECONFIG
    assert conflicts[0].owner == "Gameconfig Fix"


def test_the_first_gameconfig_mod_is_fine(install: GameInstall, game_root: Path) -> None:
    plan = _plan(game_root, _operation(install.mods_path / "update" / "gameconfig.xml"))

    assert not tuple(
        DuplicateGameConfigRule().evaluate(ConflictContext(plan=plan, install=install))
    )


def test_duplicate_textures_inside_one_package_are_informational(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    root = tmp_path / "extracted"
    package = _package(
        tmp_path,
        files=(
            _mod_file(root, "variant_a/adder2.ytd"),
            _mod_file(root, "variant_b/adder2.ytd"),
        ),
    )
    plan = _plan(game_root, _operation(install.mods_path / "a.rpf"))

    conflicts = tuple(
        DuplicateTextureRule().evaluate(
            ConflictContext(plan=plan, install=install, package=package)
        )
    )

    assert conflicts[0].severity is ConflictSeverity.INFO
    assert len(conflicts[0].paths) == 2


def test_two_operations_targeting_one_destination_are_reported(
    install: GameInstall, game_root: Path
) -> None:
    target = install.mods_path / "update" / "x64" / "dlcpacks" / "p" / "dlc.rpf"
    plan = _plan(game_root, _operation(target), _operation(target))

    conflicts = tuple(
        DuplicatePackfileRule().evaluate(ConflictContext(plan=plan, install=install))
    )

    assert conflicts[0].conflict_type is ConflictType.DUPLICATE_PACKFILE


def test_created_directories_never_count_as_duplicate_targets(
    install: GameInstall, game_root: Path
) -> None:
    folder = install.mods_path / "update"
    plan = _plan(
        game_root,
        _operation(folder, action=FileAction.CREATE_DIRECTORY),
        _operation(folder, action=FileAction.CREATE_DIRECTORY),
    )

    assert not tuple(
        DuplicatePackfileRule().evaluate(ConflictContext(plan=plan, install=install))
    )


def test_dependency_warnings_become_conflicts(
    install: GameInstall, game_root: Path
) -> None:
    plan = _plan(
        game_root,
        _operation(install.mods_path / "a.rpf"),
        dependency_warnings=("ScriptHookV is missing",),
    )

    conflicts = tuple(
        MissingDependencyRule().evaluate(ConflictContext(plan=plan, install=install))
    )

    assert conflicts[0].conflict_type is ConflictType.MISSING_DEPENDENCY
    assert conflicts[0].description == "ScriptHookV is missing"


def test_vehicle_rules_stay_silent_without_a_package(
    install: GameInstall, game_root: Path
) -> None:
    plan = _plan(game_root, _operation(install.mods_path / "a.rpf"))
    context = ConflictContext(plan=plan, install=install)

    for rule in (
        DuplicateVehicleRule(),
        DuplicateHandlingRule(),
        DuplicateDlcRule(),
        DuplicateTextureRule(),
    ):
        assert not tuple(rule.evaluate(context))


def test_the_detector_aggregates_every_rule(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    plan = _plan(
        game_root,
        _operation(game_root / "GTA5.exe", kind=InstallTarget.GAME_ROOT),
        dependency_warnings=("ScriptHookV is missing",),
    )
    package = _package(
        tmp_path,
        vehicles=VehicleManifest(
            handling=(
                HandlingDefinition(handling_id="ADDER2"),
                HandlingDefinition(handling_id="ADDER2"),
            )
        ),
    )

    report = ConflictDetector().detect(plan, install, package=package)

    kinds = {conflict.conflict_type for conflict in report.conflicts}
    assert ConflictType.PROTECTED_TARGET in kinds
    assert ConflictType.MISSING_DEPENDENCY in kinds
    assert ConflictType.DUPLICATE_HANDLING_ID in kinds
    assert report.has_blocking


def test_a_crashing_rule_does_not_hide_the_others(
    install: GameInstall, game_root: Path
) -> None:
    class Exploding(ConflictRule):
        rule_id = "conflict.exploding"

        def evaluate(self, context: ConflictContext):  # noqa: ANN202, ARG002
            raise RuntimeError("rule is broken")

    plan = _plan(
        game_root,
        _operation(game_root / "GTA5.exe", kind=InstallTarget.GAME_ROOT),
    )

    report = ConflictDetector(rules=(Exploding(), ProtectedTargetRule())).detect(
        plan, install
    )

    assert len(report.conflicts) == 1


def test_replace_model_already_in_shared_archive_is_blocking(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    archive = install.mods_path / "x64e.rpf"
    other = _installed(
        game_root,
        mod_id="other",
        name="Ferrari",
        installed_files=(
            InstalledFileRecord(
                target_path=archive,
                shared_archive=True,
                archive_members=(
                    "levels/gta5/vehicles.rpf/buffalo2.yft",
                    "levels/gta5/vehicles.rpf/buffalo2.ytd",
                ),
            ),
        ),
    )
    source = tmp_path / "buffalo2.yft"
    source.write_bytes(b"mesh")
    plan = _plan(
        game_root,
        FileOperation(
            action=FileAction.RPF_IMPORT,
            target_path=archive,
            target_kind=InstallTarget.MODS_FOLDER,
            archive_members=(
                ArchiveMemberImport(
                    source_path=source,
                    member_path="levels/gta5/vehicles.rpf/buffalo2.yft",
                ),
            ),
        ),
    )

    conflicts = tuple(
        FileOverwriteRule().evaluate(
            ConflictContext(plan=plan, install=install, installed=(other,))
        )
    )

    assert len(conflicts) == 1
    assert conflicts[0].key == "buffalo2"
    assert conflicts[0].severity is ConflictSeverity.BLOCKING
    assert conflicts[0].conflict_type is ConflictType.DUPLICATE_VEHICLE_NAME


def test_duplicate_vehicle_rule_uses_archive_member_keys(
    install: GameInstall, game_root: Path, tmp_path: Path
) -> None:
    archive = install.mods_path / "x64e.rpf"
    other = _installed(
        game_root,
        mod_id="other",
        name="Bentley",
        installed_files=(
            InstalledFileRecord(
                target_path=archive,
                shared_archive=True,
                archive_members=("levels/gta5/vehicles.rpf/cogcabrio.yft",),
            ),
        ),
    )
    source = tmp_path / "cogcabrio.yft"
    source.write_bytes(b"mesh")
    plan = _plan(
        game_root,
        FileOperation(
            action=FileAction.RPF_IMPORT,
            target_path=archive,
            target_kind=InstallTarget.MODS_FOLDER,
            archive_members=(
                ArchiveMemberImport(
                    source_path=source,
                    member_path="levels/gta5/vehicles.rpf/cogcabrio_hi.yft",
                ),
            ),
        ),
        package_id="incoming",
    )

    conflicts = tuple(
        DuplicateVehicleRule().evaluate(
            ConflictContext(plan=plan, install=install, installed=(other,))
        )
    )

    assert conflicts[0].key == "cogcabrio"
    assert conflicts[0].severity is ConflictSeverity.BLOCKING
