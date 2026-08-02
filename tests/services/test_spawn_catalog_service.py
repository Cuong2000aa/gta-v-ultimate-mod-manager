"""Tests for the Spawn Center catalog."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from gta_mod_manager.models.enums import ModStatus
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod
from gta_mod_manager.models.spawn import SpawnKind
from gta_mod_manager.services.library_service import ModSummary
from gta_mod_manager.services.spawn_catalog_service import SpawnCatalogService


class _Library:
    def __init__(self, mods: tuple[InstalledMod, ...]) -> None:
        self._mods = mods

    def list_installed(self, _install=None):
        return tuple(
            ModSummary(mod=mod, size_label="1 KB", is_intact=True) for mod in self._mods
        )


def _vehicle(root: Path) -> InstalledMod:
    return InstalledMod(
        mod_id="car1",
        display_name="Lykan",
        game_root=root,
        kind="vehicle_addon",
        spawn_codes=("lykan", "lykan2"),
        installed_at=datetime.now(UTC),
    )


def _ped(root: Path) -> InstalledMod:
    return InstalledMod(
        mod_id="ped1",
        display_name="Iron Man",
        game_root=root,
        kind="ped",
        installed_files=(
            InstalledFileRecord(
                target_path=root / "mods" / "update" / "x64" / "dlcpacks" / "umm_peds" / "dlc.rpf",
                shared_archive=True,
                archive_members=("pedmeta:ironman", "pedmeta:ironman_mk85"),
            ),
        ),
        installed_at=datetime.now(UTC),
    )


def test_catalog_lists_newest_mods_first(tmp_path: Path) -> None:
    root = tmp_path / "game"
    older = InstalledMod(
        mod_id="old",
        display_name="Old Car",
        game_root=root,
        kind="vehicle_addon",
        spawn_codes=("adder",),
        installed_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    newer = InstalledMod(
        mod_id="new",
        display_name="New Car",
        game_root=root,
        kind="vehicle_addon",
        spawn_codes=("zentorno",),
        installed_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    service = SpawnCatalogService(_Library((older, newer)))

    codes = [item.code for item in service.list_entries(kind=SpawnKind.VEHICLE)]
    assert codes == ["zentorno", "adder"]


def test_catalog_lists_vehicle_and_ped_codes(tmp_path: Path) -> None:
    root = tmp_path / "game"
    service = SpawnCatalogService(_Library((_vehicle(root), _ped(root))))

    entries = service.list_entries()

    codes = {(item.code, item.kind) for item in entries}
    assert ("lykan", SpawnKind.VEHICLE) in codes
    assert ("lykan2", SpawnKind.VEHICLE) in codes
    assert ("ironman", SpawnKind.PED) in codes
    assert ("ironman_mk85", SpawnKind.PED) in codes
    by_code = {item.code: item for item in entries}
    assert by_code["lykan"].mod_kind == "vehicle_addon"
    assert by_code["ironman"].mod_kind == "ped"


def test_catalog_includes_replace_install_kind(tmp_path: Path) -> None:
    root = tmp_path / "game"
    replace = InstalledMod(
        mod_id="rep1",
        display_name="Turismo Replace",
        game_root=root,
        kind="vehicle_replace",
        spawn_codes=("turismor",),
        installed_files=(
            InstalledFileRecord(
                target_path=root / "mods" / "x64e.rpf",
                shared_archive=True,
                archive_members=("x64/levels/gta5/vehicles.rpf/turismor.yft",),
            ),
        ),
        installed_at=datetime.now(UTC),
    )
    service = SpawnCatalogService(_Library((replace,)))
    entries = service.list_entries(kind=SpawnKind.VEHICLE)
    assert len(entries) == 1
    assert entries[0].mod_kind == "vehicle_replace"


def test_catalog_filters_by_kind_and_query(tmp_path: Path) -> None:
    root = tmp_path / "game"
    service = SpawnCatalogService(_Library((_vehicle(root), _ped(root))))

    peds = service.list_entries(kind=SpawnKind.PED)
    assert all(item.kind is SpawnKind.PED for item in peds)
    assert {item.code for item in peds} == {"ironman", "ironman_mk85"}

    hit = service.list_entries(query="lykan")
    assert {item.code for item in hit} == {"lykan", "lykan2"}

    by_mod = service.list_entries(query="iron")
    assert {item.code for item in by_mod} == {"ironman", "ironman_mk85"}


def test_disabled_mods_are_skipped(tmp_path: Path) -> None:
    root = tmp_path / "game"
    disabled = InstalledMod(
        mod_id="off",
        display_name="Off",
        game_root=root,
        kind="vehicle_addon",
        status=ModStatus.DISABLED,
        spawn_codes=("hidden",),
    )
    service = SpawnCatalogService(_Library((disabled,)))
    assert service.list_entries() == ()


def test_catalog_drops_replace_tuning_part_spawn_codes(tmp_path: Path) -> None:
    root = tmp_path / "game"
    mod = InstalledMod(
        mod_id="f250",
        display_name="F250 Super Baja",
        game_root=root,
        kind="vehicle_replace",
        spawn_codes=(
            "caracara2",
            "cara2_bumfa",
            "cara2_hooda",
            "cara2_liv1",
        ),
        installed_files=(
            InstalledFileRecord(
                target_path=root / "mods" / "x64e.rpf",
                shared_archive=True,
                archive_members=(
                    "x64e.rpf/levels/gta5/vehicles.rpf/caracara2.yft",
                    "x64e.rpf/levels/gta5/vehicles.rpf/caracara2.ytd",
                    "x64e.rpf/levels/gta5/vehicles.rpf/cara2_bumfa.yft",
                    "x64e.rpf/levels/gta5/vehicles.rpf/cara2_hooda.yft",
                    "x64e.rpf/levels/gta5/vehicles.rpf/cara2_liv1.yft",
                ),
            ),
        ),
        installed_at=datetime.now(UTC),
    )
    service = SpawnCatalogService(_Library((mod,)))
    entries = service.list_entries(kind=SpawnKind.VEHICLE)
    assert [item.code for item in entries] == ["caracara2"]


def test_ped_mod_codes_are_not_listed_as_vehicles(tmp_path: Path) -> None:
    """Ped packs often stash model names in spawn_codes — those belong on the Ped tab."""
    root = tmp_path / "game"
    mod = InstalledMod(
        mod_id="iron",
        display_name="Iron Man Mk85",
        game_root=root,
        kind="ped",
        spawn_codes=("mk85", "mk85z", "tonyae"),
        installed_files=(
            InstalledFileRecord(
                target_path=root / "mods" / "update" / "x64" / "dlcpacks" / "umm_peds" / "dlc.rpf",
                shared_archive=True,
                archive_members=("pedmeta:mk85", "pedmeta:mk85z", "pedmeta:tonyae"),
            ),
        ),
        installed_at=datetime.now(UTC),
    )
    service = SpawnCatalogService(_Library((mod,)))

    vehicles = service.list_entries(kind=SpawnKind.VEHICLE)
    peds = service.list_entries(kind=SpawnKind.PED)

    assert vehicles == ()
    assert {item.code for item in peds} == {"mk85", "mk85z", "tonyae"}
    assert all(item.kind is SpawnKind.PED for item in peds)
