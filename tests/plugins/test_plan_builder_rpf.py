"""Plan-builder coverage for automatic vehicle Replace imports."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from fivefury import RpfArchive
from fivefury.crypto import OPEN_ENCRYPTION

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.models.enums import FileAction, GamePlatform, ModKind
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.mod_package import ModPackage
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.plugins.contracts import PlanRequest
from gta_mod_manager.plugins.gta_v.plan_builder import GtaVPlanBuilder


def _write_vehicle_stream_archive(path: Path) -> None:
    with RpfArchive.empty("x64e") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/vehicles.rpf")
        nested.add("gauntlet.yft", b"VANILLA")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(path))


def _package(workspace: Path, *relative: str) -> ModPackage:
    files = []
    for rel in relative:
        absolute = workspace / rel
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(b"MODBYTES_" + rel.encode())
        files.append(
            ModFile(
                absolute_path=absolute,
                relative_path=PurePosixPath(rel),
                size_bytes=absolute.stat().st_size,
            )
        )
    inventory = FileInventory(root=workspace, files=tuple(files))
    return ModPackage(
        package_id="hellcat",
        display_name="Hellcat",
        source_path=workspace / "Hellcat.zip",
        extracted_root=workspace,
        inventory=inventory,
        classification=ModClassification(primary=ModKind.VEHICLE_REPLACE, score=0.9),
    )


def test_replace_package_plans_rpf_copy_and_import(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    (game_root / "GTA5.exe").write_bytes(b"exe")
    _write_vehicle_stream_archive(game_root / "x64e.rpf")
    mods = game_root / "mods"
    workspace = tmp_path / "workspace"
    paths = AppPaths(root=tmp_path / "appdata").ensure()

    package = _package(
        workspace,
        "Replace/gauntlet.yft",
        "Replace/gauntlet.ytd",
        "Replace/vehicles.meta",
    )
    install = GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL)
    plan = GtaVPlanBuilder().build(
        PlanRequest(package=package, install=install, paths=paths)
    )

    actions = [operation.action for operation in plan.operations]
    assert FileAction.RPF_COPY in actions
    assert FileAction.RPF_IMPORT in actions
    assert any(step.title.startswith("Import") for step in plan.manual_steps)

    imports = [op for op in plan.operations if op.action is FileAction.RPF_IMPORT]
    assert len(imports) == 1
    assert imports[0].target_path == mods / "x64e.rpf"
    assert len(imports[0].archive_members) == 2
    assert all(
        member.member_path.startswith("levels/gta5/vehicles.rpf/")
        for member in imports[0].archive_members
    )


def test_existing_mods_copy_skips_rpf_copy(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    _write_vehicle_stream_archive(game_root / "x64e.rpf")
    mods = game_root / "mods"
    mods.mkdir()
    _write_vehicle_stream_archive(mods / "x64e.rpf")
    workspace = tmp_path / "workspace"
    paths = AppPaths(root=tmp_path / "appdata").ensure()

    package = _package(workspace, "gauntlet.yft")
    install = GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL)
    plan = GtaVPlanBuilder().build(
        PlanRequest(package=package, install=install, paths=paths)
    )

    actions = [operation.action for operation in plan.operations]
    assert FileAction.RPF_COPY not in actions
    assert FileAction.RPF_IMPORT in actions


def test_plan_prefers_replace_over_backup_for_same_member(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    (game_root / "GTA5.exe").write_bytes(b"exe")
    _write_vehicle_stream_archive(game_root / "x64e.rpf")
    workspace = tmp_path / "workspace"
    paths = AppPaths(root=tmp_path / "appdata").ensure()

    package = _package(
        workspace,
        "Backup/gauntlet.yft",
        "Replace/gauntlet.yft",
        "__(Backup)/gauntlet.ytd",
        "Replace/gauntlet.ytd",
    )
    install = GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL)
    plan = GtaVPlanBuilder().build(
        PlanRequest(package=package, install=install, paths=paths)
    )

    imports = [op for op in plan.operations if op.action is FileAction.RPF_IMPORT]
    assert len(imports) == 1
    sources = {member.source_path.as_posix() for member in imports[0].archive_members}
    assert any(path.endswith("Replace/gauntlet.yft") for path in sources)
    assert any(path.endswith("Replace/gauntlet.ytd") for path in sources)
    assert not any("Backup" in path for path in sources)


def _write_mpbusiness_dlc(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with RpfArchive.empty("mpbusiness") as outer:
        _entry, nested = outer.add_nested_archive(
            "x64/levels/gta5/vehicles/mpbusinessvehicles.rpf"
        )
        nested.add("turismor.yft", b"VANILLA")
        nested.add("turismor.ytd", b"VANILLA")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(path))


def test_turismor_replace_plans_copy_of_mpbusiness_dlc(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    (game_root / "GTA5.exe").write_bytes(b"exe")
    _write_vehicle_stream_archive(game_root / "x64e.rpf")
    _write_mpbusiness_dlc(game_root / "update" / "x64" / "dlcpacks" / "mpbusiness" / "dlc.rpf")
    mods = game_root / "mods"
    workspace = tmp_path / "workspace"
    paths = AppPaths(root=tmp_path / "appdata").ensure()

    package = _package(workspace, "turismor.yft", "turismor.ytd")
    install = GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL)
    plan = GtaVPlanBuilder().build(
        PlanRequest(package=package, install=install, paths=paths)
    )

    copies = [op for op in plan.operations if op.action is FileAction.RPF_COPY]
    imports = [op for op in plan.operations if op.action is FileAction.RPF_IMPORT]
    assert copies
    assert copies[0].target_path == mods / "update" / "x64" / "dlcpacks" / "mpbusiness" / "dlc.rpf"
    assert copies[0].source_path == (
        game_root / "update" / "x64" / "dlcpacks" / "mpbusiness" / "dlc.rpf"
    )
    assert len(imports) == 1
    assert imports[0].target_path == copies[0].target_path
    assert all(
        "mpbusinessvehicles.rpf/" in member.member_path
        for member in imports[0].archive_members
    )


def _write_patchday_turismor(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with RpfArchive.empty("patchday") as outer:
        _entry, nested = outer.add_nested_archive("x64/levels/gta5/vehicles.rpf")
        nested.add("turismor.yft", b"VANILLA")
        nested.add("turismor.ytd", b"VANILLA")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(path))


def test_missing_mpbusiness_retargets_to_patchday_home(tmp_path: Path) -> None:
    """Modern installs fold Turismo R into patchday*; plan must not go empty."""
    game_root = tmp_path / "game"
    game_root.mkdir()
    (game_root / "GTA5.exe").write_bytes(b"exe")
    _write_vehicle_stream_archive(game_root / "x64e.rpf")
    _write_patchday_turismor(
        game_root / "update" / "x64" / "dlcpacks" / "patchday27ng" / "dlc.rpf"
    )
    mods = game_root / "mods"
    workspace = tmp_path / "workspace"
    paths = AppPaths(root=tmp_path / "appdata").ensure()

    package = _package(workspace, "turismor.yft", "turismor.ytd")
    install = GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL)
    plan = GtaVPlanBuilder().build(
        PlanRequest(package=package, install=install, paths=paths)
    )

    assert plan.operations
    imports = [op for op in plan.operations if op.action is FileAction.RPF_IMPORT]
    assert len(imports) == 1
    assert imports[0].target_path == (
        mods / "update" / "x64" / "dlcpacks" / "patchday27ng" / "dlc.rpf"
    )
    assert all(
        member.member_path.startswith("x64/levels/gta5/vehicles.rpf/turismor")
        for member in imports[0].archive_members
    )
    assert any("retargeted" in note.lower() or "missing" in note.lower() for note in plan.notes)
