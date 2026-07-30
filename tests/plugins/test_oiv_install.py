"""Plan-builder coverage for native OpenIV (.oiv) package installs.

An ``.oiv`` whose ``<add>`` commands target real folders (game root, scripts,
mods) is now installed automatically. Commands that write inside an ``.rpf``
still become a manual OpenIV step, and the package's own metadata/content is
never routed as loose files.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.models.classification import ModClassification
from gta_mod_manager.models.enums import FileAction, GamePlatform, InstallTarget, ModKind
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.mod_package import ModPackage
from gta_mod_manager.plugins.contracts import PlanRequest
from gta_mod_manager.plugins.gta_v.plan_builder import GtaVPlanBuilder

_ASSEMBLY_XML = """<?xml version="1.0" encoding="UTF-8"?>
<package version="2.0" target="Five">
    <metadata><name>Cool Script</name></metadata>
    <content>
        <add source="Scripts\\Cool.dll">Scripts\\Cool.dll</add>
        <add source="CoolLoader.asi">CoolLoader.asi</add>
        <add source="veh.ytd">x64\\vehicles.rpf\\veh.ytd</add>
    </content>
</package>
"""

_PACKAGE_FILES = {
    "assembly.xml": _ASSEMBLY_XML.encode(),
    "icon.png": b"PNGDATA",
    "content/Scripts/Cool.dll": b"DLL",
    "content/CoolLoader.asi": b"ASI",
    "content/veh.ytd": b"YTD",
}


def _oiv_package(workspace: Path) -> ModPackage:
    files = []
    for rel, data in _PACKAGE_FILES.items():
        absolute = workspace / rel
        absolute.parent.mkdir(parents=True, exist_ok=True)
        absolute.write_bytes(data)
        files.append(
            ModFile(
                absolute_path=absolute,
                relative_path=PurePosixPath(rel),
                size_bytes=absolute.stat().st_size,
            )
        )
    inventory = FileInventory(root=workspace, files=tuple(files))
    return ModPackage(
        package_id="cool",
        display_name="Cool Script",
        source_path=workspace / "Cool.oiv",
        extracted_root=workspace,
        inventory=inventory,
        classification=ModClassification(primary=ModKind.OPENIV_PACKAGE, score=0.9),
    )


def _build(workspace: Path, tmp_path: Path, **kwargs: object) -> object:
    game_root = tmp_path / "game"
    game_root.mkdir(exist_ok=True)
    (game_root / "GTA5.exe").write_bytes(b"exe")
    paths = AppPaths(root=tmp_path / "appdata").ensure()
    install = GameInstall(game_id="gta_v", root_path=game_root, platform=GamePlatform.MANUAL)
    request = PlanRequest(
        package=_oiv_package(workspace), install=install, paths=paths, **kwargs
    )
    return GtaVPlanBuilder().build(request)


def test_folder_targets_are_installed_automatically(tmp_path: Path) -> None:
    game_root = tmp_path / "game"
    plan = _build(tmp_path / "workspace", tmp_path)

    copied = {
        op.target_path.relative_to(game_root).as_posix(): op
        for op in plan.operations
        if op.action in (FileAction.COPY, FileAction.OVERWRITE)
    }
    assert "Scripts/Cool.dll" in copied
    assert "CoolLoader.asi" in copied
    assert copied["Scripts/Cool.dll"].target_kind is InstallTarget.SCRIPTS_FOLDER
    assert copied["CoolLoader.asi"].target_kind is InstallTarget.GAME_ROOT


def test_archive_command_becomes_a_manual_step(tmp_path: Path) -> None:
    plan = _build(tmp_path / "workspace", tmp_path)
    assert plan.requires_openiv
    assert any("need OpenIV" in step.title for step in plan.manual_steps)


def test_metadata_and_content_are_not_installed_as_loose_files(tmp_path: Path) -> None:
    plan = _build(tmp_path / "workspace", tmp_path)
    installed_sources = {
        op.source_path.name for op in plan.operations if op.source_path is not None
    }
    # The descriptor, icon and the archive-only payload must never be copied loose.
    assert "assembly.xml" not in installed_sources
    assert "icon.png" not in installed_sources
    assert "veh.ytd" not in installed_sources


def test_root_install_disabled_skips_root_and_scripts(tmp_path: Path) -> None:
    plan = _build(tmp_path / "workspace", tmp_path, allow_root_install=False)
    copies = [
        op
        for op in plan.operations
        if op.action in (FileAction.COPY, FileAction.OVERWRITE)
    ]
    assert copies == []
    assert any("root" in note.lower() for note in plan.notes)
