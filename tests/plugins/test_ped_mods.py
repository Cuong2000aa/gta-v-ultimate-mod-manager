"""Tests for character (ped) mod support.

A ped ships the same ``.yft`` / ``.ytd`` files as a car, so the danger is that
an Iron Man suit gets imported into ``levels/gta5/vehicles.rpf``. The ``.ydd``
drawable is the marker that keeps the two apart.
"""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from gta_mod_manager.analyzer.context import AnalysisContext
from gta_mod_manager.analyzer.engine import ModAnalyzer
from gta_mod_manager.analyzer.rules import default_rules
from gta_mod_manager.core.ped_assets import is_ped_asset, ped_model_stems
from gta_mod_manager.models.enums import InstallTarget, ModKind
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.plugins.gta_v.layout import PackageLayout
from gta_mod_manager.plugins.gta_v.path_mapper import GtaVPathMapper

#: The shape of the Iron Man Mk85 pack the user reported.
_IRON_MAN_FILES = (
    "MK85.ydd",
    "MK85.yft",
    "MK85.ymt",
    "MK85.ytd",
    "TonyAE.ydd",
    "TonyAE.yft",
    "TonyAE.ymt",
    "TonyAE.ytd",
    "MK85_armor.ini",
)


def _inventory(*relative_paths: str) -> FileInventory:
    """Build an inventory from package-relative paths."""
    return FileInventory(
        root=Path("workspace"),
        files=tuple(
            ModFile(
                absolute_path=Path("workspace") / path,
                relative_path=PurePosixPath(path),
                size_bytes=1,
            )
            for path in relative_paths
        ),
    )


@pytest.fixture()
def mapper() -> GtaVPathMapper:
    """Return the default path mapper."""
    return GtaVPathMapper()


def test_ped_stems_come_from_the_ydd_drawables() -> None:
    stems = ped_model_stems(_IRON_MAN_FILES)

    assert stems == {"mk85", "tonyae"}
    assert is_ped_asset("MK85.yft", stems)
    assert is_ped_asset("MK85+hi.ytd", stems)
    assert not is_ped_asset("adder.yft", stems)
    assert not is_ped_asset("MK85_armor.ini", stems)


def test_ped_meshes_are_not_imported_into_the_vehicle_archive(
    mapper: GtaVPathMapper,
) -> None:
    layout = PackageLayout.detect(_inventory(*_IRON_MAN_FILES), "Iron Man Mk85")

    assert layout.ped_model_names == {"mk85", "tonyae"}
    for name in ("MK85.yft", "MK85.ytd", "TonyAE.yft"):
        decision = mapper.decide(layout, PurePosixPath(name))
        assert decision.target is None
        assert not decision.is_archive_import
        assert decision.needs_archive_editor
        assert "ped" in decision.reason


def test_ped_armor_ini_goes_to_ironman_scripts_folder(mapper: GtaVPathMapper) -> None:
    layout = PackageLayout.detect(_inventory(*_IRON_MAN_FILES), "Iron Man Mk85")

    decision = mapper.decide(layout, PurePosixPath("MK85_armor.ini"))

    assert decision.target is InstallTarget.SCRIPTS_FOLDER
    assert decision.relative_target == Path("scripts/IronmanV Files/armors/MK85_armor.ini")


def test_a_real_vehicle_pack_still_auto_imports(mapper: GtaVPathMapper) -> None:
    layout = PackageLayout.detect(
        _inventory("adder.yft", "adder.ytd", "vehicles.meta"), "Adder Replace"
    )

    decision = mapper.decide(layout, PurePosixPath("adder.yft"))

    assert layout.ped_model_names == frozenset()
    assert decision.target is InstallTarget.MODS_FOLDER
    assert decision.archive_member_path == "levels/gta5/vehicles.rpf/adder.yft"


def test_an_addon_ped_dlc_pack_still_installs_automatically(
    mapper: GtaVPathMapper,
) -> None:
    inventory = _inventory(
        "ironman/setup2.xml",
        "ironman/content.xml",
        "ironman/dlc.rpf",
        "ironman/MK85.ydd",
        "ironman/MK85.yft",
    )
    layout = PackageLayout.detect(inventory, "Iron Man Add-On")

    decision = mapper.decide(layout, PurePosixPath("ironman/MK85.yft"))

    assert decision.target is InstallTarget.DLC_PACKS
    assert decision.relative_target == Path("update/x64/dlcpacks/ironman/MK85.yft")


def test_a_ped_pack_is_classified_as_ped_not_vehicle() -> None:
    context = AnalysisContext(
        inventory=_inventory(*_IRON_MAN_FILES), source_name="Inron man Mk85.zip"
    )

    result = ModAnalyzer(default_rules()).analyze(context.inventory, context.source_name)

    assert result.primary is ModKind.PED


def test_a_vehicle_pack_is_still_classified_as_a_vehicle() -> None:
    inventory = _inventory("adder.yft", "adder.ytd", "data/vehicles.meta")

    result = ModAnalyzer(default_rules()).analyze(inventory, "Adder Replace.zip")

    assert result.primary is ModKind.VEHICLE_REPLACE
