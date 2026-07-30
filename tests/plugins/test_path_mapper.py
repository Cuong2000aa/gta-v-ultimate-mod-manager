"""Tests for the mapping from packaged files onto installation targets."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

import pytest

from gta_mod_manager.models.enums import InstallTarget
from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.plugins.gta_v.layout import PackageLayout, strip_to_game_anchor
from gta_mod_manager.plugins.gta_v.path_mapper import GtaVPathMapper


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


def test_documentation_is_skipped(mapper: GtaVPathMapper) -> None:
    layout = PackageLayout.detect(_inventory("readme.txt"), "Mod")

    decision = mapper.decide(layout, PurePosixPath("readme.txt"))

    assert decision.target is None
    assert not decision.needs_archive_editor


def test_a_dlc_pack_lands_in_mods_dlcpacks(mapper: GtaVPathMapper) -> None:
    inventory = _inventory("adder2/setup2.xml", "adder2/content.xml", "adder2/dlc.rpf")
    layout = PackageLayout.detect(inventory, "Adder2 Addon")

    decision = mapper.decide(layout, PurePosixPath("adder2/dlc.rpf"))

    assert decision.target is InstallTarget.DLC_PACKS
    assert decision.relative_target == Path("update/x64/dlcpacks/adder2/dlc.rpf")


def test_a_package_mirroring_the_game_layout_keeps_its_structure(
    mapper: GtaVPathMapper,
) -> None:
    inventory = _inventory("mods/update/x64/dlcpacks/pack/dlc.rpf")
    layout = PackageLayout.detect(inventory, "Mirrored")

    decision = mapper.decide(layout, PurePosixPath("mods/update/x64/dlcpacks/pack/dlc.rpf"))

    assert decision.target in (InstallTarget.MODS_FOLDER, InstallTarget.DLC_PACKS)
    assert decision.relative_target == Path("update/x64/dlcpacks/pack/dlc.rpf")


def test_a_wrapped_scripts_folder_is_rebased(mapper: GtaVPathMapper) -> None:
    inventory = _inventory("Cool Script v3/scripts/Cool.dll")
    layout = PackageLayout.detect(inventory, "Cool Script")

    decision = mapper.decide(layout, PurePosixPath("Cool Script v3/scripts/Cool.dll"))

    assert decision.target is InstallTarget.SCRIPTS_FOLDER
    assert decision.relative_target == Path("scripts/Cool.dll")


def test_a_whitelisted_loose_file_goes_to_the_game_root(mapper: GtaVPathMapper) -> None:
    inventory = _inventory("Trainer/SuperPlugin.asi")
    layout = PackageLayout.detect(inventory, "Trainer")

    decision = mapper.decide(layout, PurePosixPath("Trainer/SuperPlugin.asi"))

    assert decision.target is InstallTarget.GAME_ROOT
    assert decision.relative_target == Path("SuperPlugin.asi")


def test_an_original_game_archive_is_refused(mapper: GtaVPathMapper) -> None:
    layout = PackageLayout.detect(_inventory("update.rpf"), "Patch")

    decision = mapper.decide(layout, PurePosixPath("update.rpf"))

    assert decision.target is None
    assert decision.needs_archive_editor


def test_a_loose_vehicle_asset_needs_an_archive_editor(mapper: GtaVPathMapper) -> None:
    layout = PackageLayout.detect(_inventory("adder.yft", "vehicles.meta"), "Replace")

    mesh = mapper.decide(layout, PurePosixPath("adder.yft"))
    assert mesh.target is InstallTarget.MODS_FOLDER
    assert mesh.relative_target == Path("x64e.rpf")
    assert mesh.archive_member_path == "levels/gta5/vehicles.rpf/adder.yft"
    assert not mesh.needs_archive_editor

    meta = mapper.decide(layout, PurePosixPath("vehicles.meta"))
    assert meta.target is None
    assert meta.needs_archive_editor


def test_backup_folder_stream_assets_are_skipped(mapper: GtaVPathMapper) -> None:
    inventory = _inventory(
        "Replace/gauntlet.yft",
        "Backup/gauntlet.yft",
        "__(Backup)/gauntlet.ytd",
        "original/gauntlet.yft",
        "stock/gauntlet.ytd",
    )
    layout = PackageLayout.detect(inventory, "Hellcat")

    assert mapper.decide(layout, PurePosixPath("Replace/gauntlet.yft")).is_archive_import
    for relative in (
        "Backup/gauntlet.yft",
        "__(Backup)/gauntlet.ytd",
        "original/gauntlet.yft",
        "stock/gauntlet.ytd",
    ):
        decision = mapper.decide(layout, PurePosixPath(relative))
        assert decision.target is None
        assert "Skipped" in decision.reason


def test_an_unrecognised_file_defaults_into_the_mods_folder(mapper: GtaVPathMapper) -> None:
    layout = PackageLayout.detect(_inventory("weird/thing.bin"), "Weird")

    decision = mapper.decide(layout, PurePosixPath("weird/thing.bin"))

    assert decision.target is InstallTarget.MODS_FOLDER
    assert decision.relative_target == Path("weird/thing.bin")


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("MyMod/mods/update/update.rpf", "update/update.rpf"),
        ("update/x64/dlcpacks/p/dlc.rpf", "update/x64/dlcpacks/p/dlc.rpf"),
        ("dlcpacks/p/dlc.rpf", "update/x64/dlcpacks/p/dlc.rpf"),
        ("scripts/Cool.dll", None),
    ],
)
def test_strip_to_game_anchor(path: str, expected: str | None) -> None:
    result = strip_to_game_anchor(PurePosixPath(path))

    assert result == (None if expected is None else PurePosixPath(expected))


def test_layout_detects_the_deepest_matching_pack() -> None:
    inventory = _inventory(
        "outer/dlc.rpf", "outer/inner/setup2.xml", "outer/inner/content.xml"
    )
    layout = PackageLayout.detect(inventory, "Nested")

    pack = layout.pack_for(PurePosixPath("outer/inner/content.xml"))

    assert pack is not None
    assert pack.pack_name == "inner"


def test_dual_variant_packages_skip_the_addon_half(mapper: GtaVPathMapper) -> None:
    inventory = _inventory(
        "Add-on/hellcat/dlc.rpf",
        "Replace/gauntlet.yft",
        "Replace/gauntlet.ytd",
    )
    layout = PackageLayout.detect(
        inventory,
        "Hellcat",
        selection=VariantSelection(addon=False, replace=True),
    )

    assert layout.is_dual_variant
    assert layout.prefer_replace
    assert layout.active_dlc_packs == ()
    assert layout.pack_for(PurePosixPath("Add-on/hellcat/dlc.rpf")) is None
    assert layout.is_skipped_addon_path(PurePosixPath("Add-on/hellcat/dlc.rpf"))
    assert not layout.is_skipped_replace_path(PurePosixPath("Replace/gauntlet.yft"))

    decision = mapper.decide(layout, PurePosixPath("Replace/gauntlet.yft"))
    assert decision.target is InstallTarget.MODS_FOLDER
    assert decision.is_archive_import
    assert decision.archive_member_path == "levels/gta5/vehicles.rpf/gauntlet.yft"


def test_dual_variant_requires_an_explicit_choice() -> None:
    inventory = _inventory(
        "Add-on/hellcat/dlc.rpf",
        "Replace/gauntlet.yft",
    )
    layout = PackageLayout.detect(inventory, "Hellcat")

    assert layout.is_dual_variant
    assert not layout.selection.any_selected
    assert layout.is_skipped_addon_path(PurePosixPath("Add-on/hellcat/dlc.rpf"))
    assert layout.is_skipped_replace_path(PurePosixPath("Replace/gauntlet.yft"))
    assert layout.active_dlc_packs == ()


def test_dual_variant_can_install_both_halves(mapper: GtaVPathMapper) -> None:
    inventory = _inventory(
        "Add-on/hellcat/dlc.rpf",
        "Replace/gauntlet.yft",
    )
    layout = PackageLayout.detect(
        inventory,
        "Hellcat",
        selection=VariantSelection(addon=True, replace=True),
    )

    assert not layout.is_skipped_addon_path(PurePosixPath("Add-on/hellcat/dlc.rpf"))
    assert not layout.is_skipped_replace_path(PurePosixPath("Replace/gauntlet.yft"))
    assert layout.pack_for(PurePosixPath("Add-on/hellcat/dlc.rpf")) is not None
    decision = mapper.decide(layout, PurePosixPath("Replace/gauntlet.yft"))
    assert decision.is_archive_import


def test_enhanced_is_skipped_when_legacy_is_present() -> None:
    inventory = _inventory(
        "Enhanced/Replace/caracara2.yft",
        "Legacy/Replace/caracara2.yft",
        "Legacy/Add-on/f250shelby/dlc.rpf",
        "Enhanced/Add-on/f250shelby/dlc.rpf",
    )
    layout = PackageLayout.detect(
        inventory,
        "F250",
        selection=VariantSelection(addon=True, replace=True),
    )

    assert layout.prefer_legacy_edition
    assert layout.is_skipped_edition_path(PurePosixPath("Enhanced/Replace/caracara2.yft"))
    assert not layout.is_skipped_edition_path(PurePosixPath("Legacy/Replace/caracara2.yft"))
    assert layout.pack_for(PurePosixPath("Enhanced/Add-on/f250shelby/dlc.rpf")) is None
    assert layout.pack_for(PurePosixPath("Legacy/Add-on/f250shelby/dlc.rpf")) is not None
