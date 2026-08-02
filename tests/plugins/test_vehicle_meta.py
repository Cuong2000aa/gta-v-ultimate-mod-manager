"""Tests for vehicle metadata parsing and RPF spawn-code inference."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.models.variant_selection import VariantSelection
from gta_mod_manager.plugins.gta_v.vehicle_meta import VehicleMetaParser


def _inventory(root: Path, *relative: str) -> FileInventory:
    """Build an inventory for the files already present under ``root``."""
    files = tuple(
        ModFile(
            absolute_path=root / path,
            relative_path=Path(path),
            size_bytes=(root / path).stat().st_size,
        )
        for path in relative
    )
    return FileInventory(root=root, files=files)


def test_vehicles_meta_supplies_the_spawn_code(tmp_path: Path) -> None:
    meta = (
        '<?xml version="1.0"?>\n'
        "<CVehicleModelInfo__InitDataList>\n"
        "  <InitDatas>\n"
        "    <Item>\n"
        "      <modelName>adder2</modelName>\n"
        "      <handlingId>ADDER2</handlingId>\n"
        "      <vehicleMakeName>TRUFFADE</vehicleMakeName>\n"
        "    </Item>\n"
        "  </InitDatas>\n"
        "</CVehicleModelInfo__InitDataList>\n"
    )
    path = tmp_path / "data" / "vehicles.meta"
    path.parent.mkdir(parents=True)
    path.write_text(meta, encoding="utf-8")

    manifest = VehicleMetaParser().parse(_inventory(tmp_path, "data/vehicles.meta"))

    assert manifest.spawn_codes == ("adder2",)
    assert manifest.vehicles[0].manufacturer == "TRUFFADE"


def test_spawn_codes_are_read_from_yft_names_inside_an_rpf(tmp_path: Path) -> None:
    """OpenIV add-ons bury vehicles.meta inside dlc.rpf; mesh names stay ASCII."""
    rpf = tmp_path / "lykan" / "dlc.rpf"
    rpf.parent.mkdir(parents=True)
    # Minimal fake RPF payload carrying the same strings the real Lykan pack uses,
    # including a leftover ``viper`` template that must be filtered out.
    rpf.write_bytes(
        b"\x00" * 32
        + b"vehicles.meta\x00"
        + b"lykan.yft\x00"
        + b"lykan.ytd\x00"
        + b"lykan_hi.yft\x00"
        + b"viper.yft\x00"
        + b"viper_hi.yft\x00"
        + b"Lykan Hypersport\x00"
    )

    manifest = VehicleMetaParser().parse(_inventory(tmp_path, "lykan/dlc.rpf"))

    assert manifest.spawn_codes == ("lykan",)
    assert manifest.dlc_packs[0].pack_name == "lykan"
    assert "lykan_hi" not in manifest.spawn_codes
    assert "viper" not in manifest.spawn_codes


def test_pack_folder_name_is_used_when_the_rpf_has_no_model_strings(
    tmp_path: Path,
) -> None:
    rpf = tmp_path / "zentorno2" / "dlc.rpf"
    rpf.parent.mkdir(parents=True)
    rpf.write_bytes(b"RPF7 opaque payload without model names")

    manifest = VehicleMetaParser().parse(_inventory(tmp_path, "zentorno2/dlc.rpf"))

    assert manifest.spawn_codes == ("zentorno2",)


def test_a_replacement_reports_the_vanilla_car_it_takes_over(tmp_path: Path) -> None:
    """Replacement mods ship no meta; the model file names the target car."""
    files = tmp_path / "REPLACE" / "Files"
    files.mkdir(parents=True)
    for name in ("buffalo.yft", "buffalo.ytd", "buffalo_hi.yft"):
        (files / name).write_bytes(b"asset")

    manifest = VehicleMetaParser().parse(
        _inventory(tmp_path, "REPLACE/Files/buffalo.yft", "REPLACE/Files/buffalo_hi.yft")
    )

    assert manifest.spawn_codes == ("buffalo",)


def test_a_vanilla_meta_dump_loses_against_the_shipped_models(tmp_path: Path) -> None:
    """Some authors bundle the whole vanilla vehicles.meta; it says nothing."""
    items = "".join(f"<Item><modelName>car{index}</modelName></Item>" for index in range(30))
    meta = tmp_path / "REPLACE" / "vehicles.meta"
    meta.parent.mkdir(parents=True)
    meta.write_text(f"<CVehicleModelInfo__InitDataList>{items}</CVehicleModelInfo__InitDataList>")
    (tmp_path / "REPLACE" / "buffalo2.yft").write_bytes(b"asset")

    manifest = VehicleMetaParser().parse(
        _inventory(tmp_path, "REPLACE/vehicles.meta", "REPLACE/buffalo2.yft")
    )

    assert manifest.spawn_codes == ("buffalo2",)


def test_the_replace_code_wins_when_both_routes_are_shipped(tmp_path: Path) -> None:
    """Dual-variant packs default to Replace spawn codes over Add-On ones."""
    (tmp_path / "Add-on" / "hellcat").mkdir(parents=True)
    (tmp_path / "Add-on" / "hellcat" / "dlc.rpf").write_bytes(
        b"hellcat.yft\x00hellcat.ytd\x00"
    )
    (tmp_path / "Replace").mkdir()
    (tmp_path / "Replace" / "gauntlet.yft").write_bytes(b"asset")

    inventory = _inventory(tmp_path, "Add-on/hellcat/dlc.rpf", "Replace/gauntlet.yft")
    manifest = VehicleMetaParser().parse(inventory)

    assert manifest.spawn_codes == ("gauntlet",)
    assert manifest.dlc_packs == ()

    both = VehicleMetaParser().parse(
        inventory, VariantSelection(addon=True, replace=True)
    )
    assert "gauntlet" in both.spawn_codes
    assert both.dlc_packs  # Add-On pack kept when both selected


def test_addon_only_selection_keeps_dlc_packs(tmp_path: Path) -> None:
    (tmp_path / "Add-on" / "hellcat").mkdir(parents=True)
    (tmp_path / "Add-on" / "hellcat" / "dlc.rpf").write_bytes(
        b"hellcat.yft\x00hellcat.ytd\x00"
    )
    (tmp_path / "Replace").mkdir()
    (tmp_path / "Replace" / "gauntlet.yft").write_bytes(b"asset")

    manifest = VehicleMetaParser().parse(
        _inventory(tmp_path, "Add-on/hellcat/dlc.rpf", "Replace/gauntlet.yft"),
        VariantSelection(addon=True, replace=False),
    )

    assert "gauntlet" not in manifest.spawn_codes
    assert manifest.dlc_packs


def test_tuning_parts_are_not_offered_as_spawn_codes(tmp_path: Path) -> None:
    rpf = tmp_path / "pack" / "dlc.rpf"
    rpf.parent.mkdir(parents=True)
    rpf.write_bytes(
        b"sesto.yft\x00sesto.ytd\x00"
        b"sesto_int_roll.yft\x00sesto_int_roll.ytd\x00"
        b"lp5_bon.yft\x00lp5_bon.ytd\x00"
        b"hi.yft\x00hi.ytd\x00"
    )

    manifest = VehicleMetaParser().parse(_inventory(tmp_path, "pack/dlc.rpf"))

    assert manifest.spawn_codes == ("sesto",)


def test_replace_pack_keeps_only_the_real_car_not_tuning_parts(tmp_path: Path) -> None:
    """F250-style Replace packs ship one caracara2.yft/.ytd plus dozens of parts."""
    folder = tmp_path / "Replace"
    folder.mkdir()
    (folder / "caracara2.yft").write_bytes(b"car")
    (folder / "caracara2.ytd").write_bytes(b"tex")
    for name in (
        "cara2_bumfa.yft",
        "cara2_hooda.yft",
        "cara2_liv1.yft",
        "cara2_grilla.yft",
        "cara2_winga.yft",
    ):
        (folder / name).write_bytes(b"part")

    relative = [
        "Replace/caracara2.yft",
        "Replace/caracara2.ytd",
        "Replace/cara2_bumfa.yft",
        "Replace/cara2_hooda.yft",
        "Replace/cara2_liv1.yft",
        "Replace/cara2_grilla.yft",
        "Replace/cara2_winga.yft",
    ]
    manifest = VehicleMetaParser().parse(_inventory(tmp_path, *relative))

    assert manifest.spawn_codes == ("caracara2",)
