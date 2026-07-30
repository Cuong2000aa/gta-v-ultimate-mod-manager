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


def test_catalog_lists_vehicle_and_ped_codes(tmp_path: Path) -> None:
    root = tmp_path / "game"
    service = SpawnCatalogService(_Library((_vehicle(root), _ped(root))))

    entries = service.list_entries()

    codes = {(item.code, item.kind) for item in entries}
    assert ("lykan", SpawnKind.VEHICLE) in codes
    assert ("lykan2", SpawnKind.VEHICLE) in codes
    assert ("ironman", SpawnKind.PED) in codes
    assert ("ironman_mk85", SpawnKind.PED) in codes


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
