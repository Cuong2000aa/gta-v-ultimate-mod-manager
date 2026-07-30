"""Tests for replace-vehicle key helpers."""

from gta_mod_manager.installer.vehicle_keys import (
    model_key_from_filename,
    model_keys_for_installed_mod,
    model_keys_from_archive_members,
)


def test_model_key_strips_hi_lod_suffix() -> None:
    assert model_key_from_filename("buffalo2_hi.yft") == "buffalo2"
    assert model_key_from_filename("BUFFALO2.YTD") == "buffalo2"


def test_archive_members_collapse_to_one_vehicle_key() -> None:
    keys = model_keys_from_archive_members(
        (
            "levels/gta5/vehicles.rpf/buffalo2.yft",
            "levels/gta5/vehicles.rpf/buffalo2.ytd",
            "levels/gta5/vehicles.rpf/buffalo2_hi.yft",
        )
    )
    assert keys == frozenset({"buffalo2"})


def test_installed_keys_union_spawn_and_members() -> None:
    keys = model_keys_for_installed_mod(
        ("cogcabrio",),
        ("levels/gta5/vehicles.rpf/gauntlet.yft",),
    )
    assert keys == frozenset({"cogcabrio", "gauntlet"})
