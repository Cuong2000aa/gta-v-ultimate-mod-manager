"""Tests for automatic add-on ped pack creation (AddonPeds Rebuild replacement)."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from fivefury import RpfArchive

from gta_mod_manager.core import constants
from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.enums import FileAction, GamePlatform, ModKind
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.install_plan import ArchiveMemberImport
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.mod_package import ModPackage
from gta_mod_manager.plugins.contracts import PlanRequest
from gta_mod_manager.plugins.gta_v.addon_peds import (
    import_addon_peds,
    remove_addon_peds,
)
from gta_mod_manager.plugins.gta_v.plan_builder import GtaVPlanBuilder
from tests.helpers.rpf_fixtures import write_minimal_update_rpf


def _write_ped_files(workspace: Path, *names: str) -> list[Path]:
    paths = []
    for name in names:
        path = workspace / name
        path.write_bytes(b"PED_" + name.encode())
        paths.append(path)
    return paths


def test_import_creates_umm_peds_pack_with_meta(tmp_path: Path) -> None:
    workspace = tmp_path / "src"
    workspace.mkdir()
    files = _write_ped_files(workspace, "MK85.ydd", "MK85.yft", "MK85.ymt", "MK85.ytd")
    dlc = tmp_path / "umm_peds" / "dlc.rpf"

    stems = import_addon_peds(
        dlc,
        tuple(
            ArchiveMemberImport(source_path=path, member_path=f"peds.rpf/{path.name}")
            for path in files
        ),
    )

    assert stems == ("mk85",)
    assert dlc.is_file()
    with RpfArchive.from_path(str(dlc)) as archive:
        names = {entry.name for entry in archive.iter_entries()}
        assert "setup2.xml" in names
        assert "content.xml" in names
        assert "peds.meta" in names
        assert "peds.rpf" in names
        meta = archive.read_entry_bytes(archive.find_entry("peds.meta")).decode("utf-8")
        assert "<Name>mk85</Name>" in meta
        nested = archive.load_nested_archive(archive.find_entry("peds.rpf"))
        assert {entry.name for entry in nested.iter_entries()} == {
            "MK85.ydd",
            "MK85.yft",
            "MK85.ymt",
            "MK85.ytd",
        }


def test_remove_addon_peds_scrubs_meta_and_stream(tmp_path: Path) -> None:
    workspace = tmp_path / "src"
    workspace.mkdir()
    files = _write_ped_files(
        workspace,
        "MK85.ydd",
        "MK85.yft",
        "TonyAE.ydd",
        "TonyAE.yft",
    )
    dlc = tmp_path / "umm_peds" / "dlc.rpf"
    import_addon_peds(
        dlc,
        tuple(
            ArchiveMemberImport(source_path=path, member_path=f"peds.rpf/{path.name}")
            for path in files
        ),
    )

    removed = remove_addon_peds(dlc, ["mk85"])

    assert removed == 1
    with RpfArchive.from_path(str(dlc)) as archive:
        meta = archive.read_entry_bytes(archive.find_entry("peds.meta")).decode("utf-8")
        assert "<Name>mk85</Name>" not in meta
        assert "<Name>tonyae</Name>" in meta
        nested = archive.load_nested_archive(archive.find_entry("peds.rpf"))
        left = {entry.name for entry in nested.iter_entries()}
        assert left == {"TonyAE.ydd", "TonyAE.yft"}


def test_plan_builder_auto_imports_peds_without_manual_step(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    game_root.mkdir()
    (game_root / "GTA5.exe").write_bytes(b"exe")
    write_minimal_update_rpf(game_root / "update" / "update.rpf")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    for name in ("MK85.ydd", "MK85.yft", "MK85.ymt", "MK85.ytd", "MK85_armor.ini"):
        (workspace / name).write_bytes(b"x")

    files = tuple(
        ModFile(
            absolute_path=workspace / name,
            relative_path=PurePosixPath(name),
            size_bytes=1,
        )
        for name in ("MK85.ydd", "MK85.yft", "MK85.ymt", "MK85.ytd", "MK85_armor.ini")
    )
    package = ModPackage(
        package_id="iron",
        display_name="Iron Man Mk85",
        source_path=workspace / "iron.zip",
        extracted_root=workspace,
        inventory=FileInventory(root=workspace, files=files),
        classification=ModClassification(primary=ModKind.PED, score=0.9),
    )
    paths = AppPaths(root=tmp_path / "appdata").ensure()
    install = GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL)
    plan = GtaVPlanBuilder().build(PlanRequest(package=package, install=install, paths=paths))

    actions = [op.action for op in plan.operations]
    assert FileAction.RPF_PED_IMPORT in actions
    assert FileAction.RPF_DLC_REGISTER in actions
    assert not any("character (ped)" in step.title.lower() for step in plan.manual_steps)

    armor = [
        op
        for op in plan.operations
        if op.source_path is not None and op.source_path.name == "MK85_armor.ini"
    ]
    assert len(armor) == 1
    assert armor[0].target_path == (
        game_root / "scripts" / "IronmanV Files" / "armors" / "MK85_armor.ini"
    )

    ped_import = next(op for op in plan.operations if op.action is FileAction.RPF_PED_IMPORT)
    assert ped_import.target_path == (
        game_root
        / constants.MODS_FOLDER_NAME
        / Path(*constants.DLC_PACKS_RELATIVE.split("/"))
        / constants.ADDON_PEDS_PACK_NAME
        / "dlc.rpf"
    )
