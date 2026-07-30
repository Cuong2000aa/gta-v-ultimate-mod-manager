"""Tests for orphan DLC / broken vehicle-stream diagnostics."""

from __future__ import annotations

from pathlib import Path

from fivefury import RpfArchive
from fivefury.crypto import OPEN_ENCRYPTION
from fivefury.rpf.entries import RpfBinaryFileEntry, RpfResourceFileEntry
from fivefury.rpf.utils import _build_rsc7, _resource_flags_from_size

from gta_mod_manager.diagnostics.actions import (
    FIX_DELETE_ORPHAN_DLCPACKS,
    FIX_RESTORE_VEHICLE_STREAM,
)
from gta_mod_manager.diagnostics.repairs import apply_diagnostic_fix
from gta_mod_manager.diagnostics.scanner import DiagnosticsScanner
from gta_mod_manager.diagnostics.vehicle_checks import (
    find_bad_vehicle_stream_entries,
    find_orphan_dlcpacks,
)
from gta_mod_manager.models.diagnostic import DiagnosticSeverity
from gta_mod_manager.models.enums import GamePlatform
from gta_mod_manager.models.game_install import GameInstall
from gta_mod_manager.models.mod_package import InstalledFileRecord, InstalledMod


def _install(root: Path) -> GameInstall:
    (root / "GTA5.exe").write_bytes(b"exe")
    return GameInstall(game_id="gta_v", root_path=root, platform=GamePlatform.STEAM)


def _rsc7_blob(payload: bytes = b"STOCK_MESH_BYTES") -> bytes:
    sys_flags = _resource_flags_from_size(len(payload))
    return _build_rsc7(payload, version=165, sys_flags=sys_flags, gfx_flags=0)


def _write_x64e(path: Path, *, members: dict[str, bytes]) -> None:
    with RpfArchive.empty("x64e") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/vehicles.rpf")
        for name, data in members.items():
            nested.add(name, data)
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(path))


def test_detects_orphan_hellcat_dlcpack(tmp_path: Path) -> None:
    root = tmp_path / "game"
    orphan = root / "mods" / "update" / "x64" / "dlcpacks" / "hellcat"
    orphan.mkdir(parents=True)
    (orphan / "dlc.rpf").write_bytes(b"dlc")

    tracked = InstalledMod(
        mod_id="other",
        display_name="Other",
        game_root=root,
        kind="vehicle_addon",
        dlc_packs=("adder2",),
    )
    found = find_orphan_dlcpacks(root, (tracked,))
    assert [item.pack_name for item in found] == ["hellcat"]

    report = DiagnosticsScanner().scan(_install(root), installed_mods=(tracked,))
    finding = next(item for item in report.findings if item.code == "mods.orphan_dlcpack")
    assert finding.severity is DiagnosticSeverity.WARNING
    assert finding.fix_action == FIX_DELETE_ORPHAN_DLCPACKS
    assert finding.fix_targets == ("hellcat",)
    assert finding.is_fixable
    assert "hellcat" in finding.title.lower()


def test_tracked_dlcpack_is_not_orphan(tmp_path: Path) -> None:
    root = tmp_path / "game"
    pack = root / "mods" / "update" / "x64" / "dlcpacks" / "hellcat"
    pack.mkdir(parents=True)
    tracked = InstalledMod(
        mod_id="hellcat",
        display_name="Hellcat",
        game_root=root,
        kind="vehicle_addon",
        dlc_packs=("hellcat",),
    )
    assert find_orphan_dlcpacks(root, (tracked,)) == ()


def test_known_external_packs_are_not_orphans(tmp_path: Path) -> None:
    root = tmp_path / "game"
    packs = root / "mods" / "update" / "x64" / "dlcpacks"
    for name in ("pedselector", "umm_peds", "addonpeds", "straypack"):
        folder = packs / name
        folder.mkdir(parents=True)
        (folder / "dlc.rpf").write_bytes(b"x")

    found = find_orphan_dlcpacks(root, ())
    assert [item.pack_name for item in found] == ["straypack"]


def test_detects_binary_vehicle_stream_entries(tmp_path: Path) -> None:
    root = tmp_path / "game"
    mods = root / "mods"
    mods.mkdir(parents=True)
    # Plain bytes → RpfBinaryFileEntry (the bad post-uninstall pattern).
    _write_x64e(
        mods / "x64e.rpf",
        members={
            "gauntlet.yft": b"NOT_A_RESOURCE",
            "baller.ytd": b"ALSO_BINARY",
            "readme.txt": b"ignore me",
        },
    )

    bad = find_bad_vehicle_stream_entries(mods / "x64e.rpf")
    names = {Path(item.member_path).name for item in bad}
    assert names == {"gauntlet.yft", "baller.ytd"}
    assert all(item.entry_type == "RpfBinaryFileEntry" for item in bad)

    report = DiagnosticsScanner().scan(_install(root))
    finding = next(item for item in report.findings if item.code == "mods.bad_vehicle_stream")
    assert finding.severity is DiagnosticSeverity.ERROR
    assert finding.fix_action == FIX_RESTORE_VEHICLE_STREAM
    assert any("gauntlet.yft" in target for target in finding.fix_targets)


def test_resource_vehicle_stream_is_healthy(tmp_path: Path) -> None:
    archive = tmp_path / "x64e.rpf"
    _write_x64e(archive, members={"gauntlet.yft": _rsc7_blob()})
    with RpfArchive.from_path(str(archive)) as loaded:
        nested = loaded.load_nested_archive(loaded.find_entry("levels/gta5/vehicles.rpf"))
        entry = next(item for item in nested.iter_entries() if item.name == "gauntlet.yft")
        assert isinstance(entry, RpfResourceFileEntry)
    assert find_bad_vehicle_stream_entries(archive) == ()


def test_repair_deletes_orphan_dlcpack(tmp_path: Path) -> None:
    root = tmp_path / "game"
    orphan = root / "mods" / "update" / "x64" / "dlcpacks" / "hellcat"
    orphan.mkdir(parents=True)
    (orphan / "dlc.rpf").write_bytes(b"dlc")

    result = apply_diagnostic_fix(root, FIX_DELETE_ORPHAN_DLCPACKS, ("hellcat",))
    assert result.is_ok
    assert not orphan.exists()


def test_repair_restores_stock_vehicle_stream(tmp_path: Path) -> None:
    root = tmp_path / "game"
    root.mkdir()
    mods = root / "mods"
    mods.mkdir()
    stock_blob = _rsc7_blob(b"STOCK_GAUNTLET")
    _write_x64e(root / "x64e.rpf", members={"gauntlet.yft": stock_blob})
    _write_x64e(mods / "x64e.rpf", members={"gauntlet.yft": b"BROKEN_BINARY"})

    member = "levels/gta5/vehicles.rpf/gauntlet.yft"
    result = apply_diagnostic_fix(root, FIX_RESTORE_VEHICLE_STREAM, (member,))
    assert result.is_ok, result.error

    with RpfArchive.from_path(str(mods / "x64e.rpf")) as loaded:
        nested = loaded.load_nested_archive(loaded.find_entry("levels/gta5/vehicles.rpf"))
        entry = next(item for item in nested.iter_entries() if item.name == "gauntlet.yft")
        assert isinstance(entry, RpfResourceFileEntry)
        assert not isinstance(entry, RpfBinaryFileEntry)

    assert find_bad_vehicle_stream_entries(mods / "x64e.rpf") == ()


def test_unhealthy_replace_member_finding(tmp_path: Path) -> None:
    root = tmp_path / "game"
    mods = root / "mods"
    mods.mkdir(parents=True)
    _write_x64e(mods / "x64e.rpf", members={"adder.yft": _rsc7_blob()})

    mod = InstalledMod(
        mod_id="replace1",
        display_name="Gauntlet Replace",
        game_root=root,
        kind="vehicle_replace",
        installed_files=(
            InstalledFileRecord(
                target_path=mods / "x64e.rpf",
                shared_archive=True,
                archive_members=("levels/gta5/vehicles.rpf/gauntlet.yft",),
            ),
        ),
    )
    report = DiagnosticsScanner().scan(_install(root), installed_mods=(mod,))
    finding = next(
        item for item in report.findings if item.code == "mods.replace_members_unhealthy"
    )
    assert finding.severity is DiagnosticSeverity.WARNING
    assert finding.is_fixable
