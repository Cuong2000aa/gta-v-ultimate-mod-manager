"""Tests for dual Add-On / Replace selection during install planning."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.enums import FileAction, GamePlatform, ModKind
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.mod_package import ModPackage
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.plugins.contracts import PlanRequest
from gta_mod_manager.plugins.gta_v.plugin import GtaVPlugin


def _package(root: Path, *relative: str) -> ModPackage:
    files = []
    for path in relative:
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.write_bytes(b"data")
        files.append(
            ModFile(
                absolute_path=target,
                relative_path=Path(path),
                size_bytes=target.stat().st_size,
            )
        )
    inventory = FileInventory(root=root, files=tuple(files))
    return ModPackage(
        package_id="dual",
        display_name="Dual Pack",
        source_path=root / "Dual.zip",
        extracted_root=root,
        inventory=inventory,
        classification=ModClassification(primary=ModKind.VEHICLE_REPLACE, score=0.8),
    )


def test_plan_installs_only_selected_half(tmp_path: Path) -> None:
    pack = tmp_path / "pkg"
    package = _package(
        pack,
        "Add-on/hellcat/dlc.rpf",
        "Replace/gauntlet.yft",
    )
    game_root = tmp_path / "game"
    game_root.mkdir()
    (game_root / "GTA5.exe").write_bytes(b"exe")
    (game_root / "x64e.rpf").write_bytes(b"rpf")
    (game_root / "mods").mkdir()
    install = GameInstall(
        game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL
    )
    plugin = GtaVPlugin()
    paths = AppPaths(tmp_path / "app").ensure()

    def _actions(plan) -> set[FileAction]:
        return {op.action for op in plan.operations}

    def _copies_addon(plan) -> bool:
        return any(
            op.action in {FileAction.COPY, FileAction.OVERWRITE}
            and op.target_path.name.lower() == "dlc.rpf"
            and "dlcpacks" in op.target_path.parts
            for op in plan.operations
        )

    replace_plan = plugin.build_install_plan(
        PlanRequest(
            package=package,
            install=install,
            paths=paths,
            variants=VariantSelection(addon=False, replace=True),
        )
    )
    assert FileAction.RPF_IMPORT in _actions(replace_plan)
    assert not _copies_addon(replace_plan)

    addon_plan = plugin.build_install_plan(
        PlanRequest(
            package=package,
            install=install,
            paths=paths,
            variants=VariantSelection(addon=True, replace=False),
        )
    )
    assert _copies_addon(addon_plan)
    assert FileAction.RPF_IMPORT not in _actions(addon_plan)

    both_plan = plugin.build_install_plan(
        PlanRequest(
            package=package,
            install=install,
            paths=paths,
            variants=VariantSelection(addon=True, replace=True),
        )
    )
    assert FileAction.RPF_IMPORT in _actions(both_plan)
    assert _copies_addon(both_plan)

    none_plan = plugin.build_install_plan(
        PlanRequest(
            package=package,
            install=install,
            paths=paths,
            variants=VariantSelection(addon=False, replace=False),
        )
    )
    assert none_plan.is_empty
