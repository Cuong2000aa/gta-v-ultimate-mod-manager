"""Tests for spawn-code extraction from ReadMe / INSTALL documents."""

from __future__ import annotations

from pathlib import Path

from gta_mod_manager.models.mod_file import FileInventory, ModFile
from gta_mod_manager.plugins.gta_v import readme_spawn
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


def test_spawn_by_name_colon_is_recognised(tmp_path: Path) -> None:
    path = tmp_path / "ReadMe.txt"
    path.write_text("8. Use Menyoo or Simple Trainer and spawn it by name: hellcat\n")

    assert readme_spawn.extract_spawn_codes(_inventory(tmp_path, "ReadMe.txt")) == (
        ("hellcat", path),
    )


def test_quoted_type_name_is_recognised(tmp_path: Path) -> None:
    path = tmp_path / "ADD-ON" / "INSTRUCTION.txt"
    path.parent.mkdir()
    path.write_text('select "spawn by name" and type "fpino"\n')

    codes = readme_spawn.extract_spawn_codes(_inventory(tmp_path, "ADD-ON/INSTRUCTION.txt"))

    assert codes == (("fpino", path),)


def test_spawn_name_is_phrase_is_recognised(tmp_path: Path) -> None:
    path = tmp_path / "Addon" / "Readme.txt"
    path.parent.mkdir(parents=True)
    path.write_text("Spawn name is LP580\nenjoy\n")

    codes = readme_spawn.extract_spawn_codes(_inventory(tmp_path, "Addon/Readme.txt"))

    assert codes == (("lp580", path),)


def test_bracket_spawncode_is_recognised(tmp_path: Path) -> None:
    path = tmp_path / "Readme.txt"
    path.write_text("[spawncode] = amrevu23mg\n")

    codes = readme_spawn.extract_spawn_codes(_inventory(tmp_path, "Readme.txt"))

    assert codes == (("amrevu23mg", path),)


def test_type_this_name_accepts_leading_digits(tmp_path: Path) -> None:
    path = tmp_path / "ReadmeADDON.txt"
    path.write_text(
        "2010 Dodge Ram 3500  --------> Type this name: 10ram\n"
        "PJ Trailer --------> Type this name: pjtrailer\n"
    )

    codes = dict(readme_spawn.extract_spawn_codes(_inventory(tmp_path, "ReadmeADDON.txt")))

    assert codes == {"10ram": path, "pjtrailer": path}


def test_use_the_name_dash_is_recognised(tmp_path: Path) -> None:
    path = tmp_path / "ADD ON Readme - English.txt"
    path.write_text("3. To spawn the car, use the name - ben17\n")

    codes = readme_spawn.extract_spawn_codes(
        _inventory(tmp_path, "ADD ON Readme - English.txt")
    )

    assert codes == (("ben17", path),)


def test_readme_spawn_beats_noisy_rpf_names(tmp_path: Path) -> None:
    """Authors write the real spawn name; the RPF still contains template cars."""
    readme = tmp_path / "Add-On" / "Instalation.txt"
    readme.parent.mkdir(parents=True)
    readme.write_text("5) Spawn it with name: sesto\n")
    rpf = tmp_path / "Add-On" / "sestoelemento" / "dlc.rpf"
    rpf.parent.mkdir(parents=True)
    rpf.write_bytes(b"sesto.yft\x00sesto.ytd\x00vacca.yft\x00vacca.ytd\x00r8ppi.yft\x00r8ppi.ytd\x00")

    manifest = VehicleMetaParser().parse(
        _inventory(tmp_path, "Add-On/Instalation.txt", "Add-On/sestoelemento/dlc.rpf")
    )

    assert manifest.spawn_codes == ("sesto",)
    assert manifest.vehicles[0].source_file == readme


def test_readme_spawn_beats_a_replace_vehicles_meta(tmp_path: Path) -> None:
    """Add-on-only packages still trust the readme over a replace-style meta dump."""
    readme = tmp_path / "installation.txt"
    readme.write_text("use simple native trainer to spawn the car by name 570s2\n")
    meta = tmp_path / "data" / "vehicles.meta"
    meta.parent.mkdir(parents=True)
    meta.write_text(
        "<CVehicleModelInfo__InitDataList><InitDatas>"
        "<Item><modelName>t20</modelName></Item>"
        "<Item><modelName>brawler</modelName></Item>"
        "</InitDatas></CVehicleModelInfo__InitDataList>"
    )

    manifest = VehicleMetaParser().parse(
        _inventory(tmp_path, "installation.txt", "data/vehicles.meta")
    )

    assert manifest.spawn_codes == ("570s2",)


def test_dual_variant_packages_prefer_the_replace_half(tmp_path: Path) -> None:
    """When Add-On and Replace both exist, Replace spawn codes win."""
    addon_readme = tmp_path / "Add-on" / "installation.txt"
    addon_readme.parent.mkdir(parents=True)
    addon_readme.write_text("spawn the car by name 570s2\n")
    (tmp_path / "Add-on" / "adimods").mkdir()
    (tmp_path / "Add-on" / "adimods" / "dlc.rpf").write_bytes(b"rpf")
    replace = tmp_path / "Replace"
    replace.mkdir()
    (replace / "t20.yft").write_bytes(b"asset")

    manifest = VehicleMetaParser().parse(
        _inventory(
            tmp_path,
            "Add-on/installation.txt",
            "Add-on/adimods/dlc.rpf",
            "Replace/t20.yft",
        )
    )

    assert manifest.spawn_codes == ("t20",)
    assert manifest.dlc_packs == ()



def test_openiv_search_and_type_is_not_a_spawn_code(tmp_path: Path) -> None:
    path = tmp_path / "INSTRUCTION.txt"
    path.write_text(
        'Use "Search" and type "feltzer"\n'
        'Here replace "feltzer2.ytd" / "feltzer2.yft"\n'
        'SPAWN THE CAR: type "gtr"\n'
    )

    codes = dict(readme_spawn.extract_spawn_codes(_inventory(tmp_path, "INSTRUCTION.txt")))

    assert "feltzer" not in codes
    assert codes.get("gtr") == path
