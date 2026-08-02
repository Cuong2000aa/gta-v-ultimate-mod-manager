"""Tests for DLC-pack vehicle replace target resolution."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.plugins.gta_v.layout import PackageLayout
from gta_mod_manager.plugins.gta_v.path_mapper import GtaVPathMapper
from gta_mod_manager.plugins.gta_v.replace_targets import (
    target_from_path_text,
    target_from_stock_home,
)


def _inventory(root: Path, *relative: str) -> FileInventory:
    files = []
    for path in relative:
        absolute = root / path
        absolute.parent.mkdir(parents=True, exist_ok=True)
        if not absolute.exists():
            absolute.write_text("placeholder\n", encoding="utf-8")
        files.append(
            ModFile(
                absolute_path=absolute,
                relative_path=PurePosixPath(path),
                size_bytes=absolute.stat().st_size,
            )
        )
    return FileInventory(root=root, files=tuple(files))


def test_stock_home_maps_turismor_to_mpbusiness() -> None:
    target = target_from_stock_home("turismor_hi.yft")
    assert target is not None
    assert target.pack_name == "mpbusiness"
    assert target.relative_archive == Path("update/x64/dlcpacks/mpbusiness/dlc.rpf")
    assert target.member_path("turismor.yft").endswith(
        "mpbusinessvehicles.rpf/turismor.yft"
    )


def test_parse_openiv_path_with_x64w_prefix() -> None:
    target = target_from_path_text(
        r"x64w.rpf\dlcpacks\mpbusiness\dlc.rpf\x64\levels\gta5\vehicles\mpbusinessvehicles.rpf\\"
    )
    assert target is not None
    assert target.pack_name == "mpbusiness"
    assert target.nested_rpf.endswith("mpbusinessvehicles.rpf")


def test_flat_turismor_uses_stock_dlc_home(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, "turismor.yft", "turismor.ytd")
    layout = PackageLayout.detect(inventory, "LaFerrari")
    mapper = GtaVPathMapper()

    decision = mapper.decide(layout, PurePosixPath("turismor.yft"))

    assert decision.is_archive_import
    assert decision.relative_target == Path("update/x64/dlcpacks/mpbusiness/dlc.rpf")
    assert decision.archive_member_path == (
        "x64/levels/gta5/vehicles/mpbusinessvehicles.rpf/turismor.yft"
    )


def test_embedded_dlc_path_beats_loose_game_structure(tmp_path: Path) -> None:
    relative = (
        "x64w.rpf/dlcpacks/mpbusiness/dlc.rpf/x64/levels/gta5/vehicles/"
        "mpbusinessvehicles.rpf/turismor.yft"
    )
    inventory = _inventory(tmp_path, relative)
    layout = PackageLayout.detect(inventory, "LaFerrari")
    mapper = GtaVPathMapper()

    decision = mapper.decide(layout, PurePosixPath(relative))

    assert decision.relative_target == Path("update/x64/dlcpacks/mpbusiness/dlc.rpf")
    assert decision.archive_member_path.endswith("mpbusinessvehicles.rpf/turismor.yft")


def test_readme_directory_path_applies_to_flat_assets(tmp_path: Path) -> None:
    readme = tmp_path / "ReadMe.txt"
    readme.write_text(
        "Installation:\n"
        "place the car files in: "
        "x64w.rpf\\dlcpacks\\mpbusiness\\dlc.rpf\\"
        "x64\\levels\\gta5\\vehicles\\mpbusinessvehicles.rpf\\\n",
        encoding="utf-8",
    )
    (tmp_path / "turismor.yft").write_bytes(b"car")
    inventory = FileInventory(
        root=tmp_path,
        files=(
            ModFile(
                absolute_path=readme,
                relative_path=PurePosixPath("ReadMe.txt"),
                size_bytes=readme.stat().st_size,
            ),
            ModFile(
                absolute_path=tmp_path / "turismor.yft",
                relative_path=PurePosixPath("turismor.yft"),
                size_bytes=3,
            ),
        ),
    )
    layout = PackageLayout.detect(inventory, "LaFerrari")
    assert "*" in layout.dlc_replace_hints or "turismor.yft" in layout.dlc_replace_hints

    decision = GtaVPathMapper().decide(layout, PurePosixPath("turismor.yft"))
    assert decision.relative_target == Path("update/x64/dlcpacks/mpbusiness/dlc.rpf")


def test_buffalo2_still_targets_x64e(tmp_path: Path) -> None:
    inventory = _inventory(tmp_path, "Replace/buffalo2.yft")
    layout = PackageLayout.detect(inventory, "Buffalo")
    decision = GtaVPathMapper().decide(layout, PurePosixPath("Replace/buffalo2.yft"))

    assert decision.relative_target == Path("x64e.rpf")
    assert decision.archive_member_path == "levels/gta5/vehicles.rpf/buffalo2.yft"
