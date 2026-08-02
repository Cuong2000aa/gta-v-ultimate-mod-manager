"""Tests for OpenIV virtual path → mods RPF mapping."""

from __future__ import annotations

from pathlib import Path, PurePosixPath

from gta_mod_manager.plugins.gta_v.oiv_targets import resolve_openiv_virtual_path


def test_common_data_maps_to_update_rpf() -> None:
    target = resolve_openiv_virtual_path(PurePosixPath("/common/data/handling.meta"))
    assert target is not None
    assert target.relative_archive == Path("update/update.rpf")
    assert target.member_path == "common/data/handling.meta"
    assert target.is_dlc_patch is False


def test_x64_data_maps_to_update_rpf() -> None:
    target = resolve_openiv_virtual_path(PurePosixPath("/x64/data/carvariations.ymt"))
    assert target is not None
    assert target.relative_archive == Path("update/update.rpf")
    assert target.member_path == "x64/data/carvariations.ymt"


def test_dlc_patch_maps_to_pack_dlc_rpf() -> None:
    target = resolve_openiv_virtual_path(
        PurePosixPath("/dlc_patch/mpapartment/common/data/carvariations.meta")
    )
    assert target is not None
    assert target.relative_archive == Path(
        "update/x64/dlcpacks/mpapartment/dlc.rpf"
    )
    assert target.member_path == "common/data/carvariations.meta"
    assert target.is_dlc_patch is True


def test_unknown_virtual_path_returns_none() -> None:
    assert resolve_openiv_virtual_path(PurePosixPath("/scripts/foo.asi")) is None
