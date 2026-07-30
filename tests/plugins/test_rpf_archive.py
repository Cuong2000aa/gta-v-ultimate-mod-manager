"""Unit tests for mods-folder RPF member imports."""

from __future__ import annotations

from pathlib import Path

import pytest
from fivefury import RpfArchive
from fivefury.crypto import OPEN_ENCRYPTION

from gta_mod_manager.core.exceptions import InstallError
from gta_mod_manager.models.install_plan import ArchiveMemberImport
from gta_mod_manager.plugins.gta_v.rpf_archive import import_members, split_member_path


def _write_vehicle_stream_archive(path: Path) -> None:
    """Create a tiny OPEN x64e.rpf with a nested vehicles.rpf."""
    with RpfArchive.empty("x64e") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/vehicles.rpf")
        nested.add("adder.yft", b"VANILLA_ADDER_YFT")
        nested.add("adder.ytd", b"VANILLA_ADDER_YTD")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(path))


def test_split_member_path_detects_nested_archives() -> None:
    nested, leaf = split_member_path("levels/gta5/vehicles.rpf/gauntlet.yft")
    assert nested == "levels/gta5/vehicles.rpf"
    assert leaf == "gauntlet.yft"


def test_split_member_path_outer_only() -> None:
    nested, leaf = split_member_path("readme.txt")
    assert nested is None
    assert leaf == "readme.txt"


def test_import_members_replaces_nested_vehicle_assets(tmp_path: Path) -> None:
    archive = tmp_path / "x64e.rpf"
    _write_vehicle_stream_archive(archive)
    original_hash = archive.read_bytes()

    source = tmp_path / "gauntlet.yft"
    source.write_bytes(b"REPLACE_GAUNTLET_MESH")

    import_members(
        archive,
        (
            ArchiveMemberImport(
                source_path=source,
                member_path="levels/gta5/vehicles.rpf/gauntlet.yft",
            ),
        ),
    )

    assert archive.read_bytes() != original_hash
    with RpfArchive.from_path(str(archive)) as loaded:
        entry = loaded.find_entry("levels/gta5/vehicles.rpf")
        assert entry is not None
        nested = loaded.load_nested_archive(entry)
        names = sorted(item.name for item in nested.iter_entries())
        assert "gauntlet.yft" in names
        assert "adder.yft" in names


def test_import_members_converts_ng_nested_archive(tmp_path: Path) -> None:
    """Stock nested RPFs may report NG; save must force OPEN on the tree."""
    from fivefury.crypto import NG_ENCRYPTION

    from gta_mod_manager.plugins.gta_v.rpf_archive import force_open_encryption

    archive = tmp_path / "x64e.rpf"
    _write_vehicle_stream_archive(archive)
    source = tmp_path / "gauntlet.yft"
    source.write_bytes(b"REPLACE_GAUNTLET_MESH")

    # Simulate the real failure mode: nested still NG while saving.
    with RpfArchive.from_path(str(archive)) as loaded:
        entry = loaded.find_entry("levels/gta5/vehicles.rpf")
        assert entry is not None
        nested = loaded.load_nested_archive(entry)
        assert nested is not None
        nested.encryption = NG_ENCRYPTION
        loaded.encryption = NG_ENCRYPTION
        nested.add("gauntlet.yft", source.read_bytes())
        assert force_open_encryption(loaded) is True
        loaded.save(str(archive))

    with RpfArchive.from_path(str(archive)) as verify:
        assert verify.encryption == OPEN_ENCRYPTION
        entry = verify.find_entry("levels/gta5/vehicles.rpf")
        nested = verify.load_nested_archive(entry)
        assert nested is not None
        names = {item.name for item in nested.iter_entries()}
        assert "gauntlet.yft" in names


def test_import_members_through_public_api_with_ng_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """import_members must convert NG before save, not only set outer OPEN."""
    from fivefury.crypto import NG_ENCRYPTION

    archive = tmp_path / "x64e.rpf"
    _write_vehicle_stream_archive(archive)
    source = tmp_path / "gauntlet.yft"
    source.write_bytes(b"REPLACE_VIA_API")

    real_from_path = RpfArchive.from_path

    def _from_path_marking_ng(path: str, **kwargs: object) -> RpfArchive:
        loaded = real_from_path(path, **kwargs)
        loaded.encryption = NG_ENCRYPTION
        return loaded

    monkeypatch.setattr(RpfArchive, "from_path", staticmethod(_from_path_marking_ng))
    # Also mark nested NG after load.
    real_load = RpfArchive.load_nested_archive

    def _load_nested(self: RpfArchive, entry: object, **kwargs: object) -> RpfArchive | None:
        nested = real_load(self, entry, **kwargs)
        if nested is not None:
            nested.encryption = NG_ENCRYPTION
        return nested

    monkeypatch.setattr(RpfArchive, "load_nested_archive", _load_nested)

    import_members(
        archive,
        (
            ArchiveMemberImport(
                source_path=source,
                member_path="levels/gta5/vehicles.rpf/gauntlet.yft",
            ),
        ),
    )

    with real_from_path(str(archive)) as verify:
        assert verify.encryption == OPEN_ENCRYPTION
        entry = verify.find_entry("levels/gta5/vehicles.rpf")
        nested = verify.load_nested_archive(entry)
        assert nested is not None
        assert "gauntlet.yft" in {item.name for item in nested.iter_entries()}


def test_restore_stock_members_overwrites_modded_adder(tmp_path: Path) -> None:
    from fivefury.rpf.entries import RpfResourceFileEntry
    from fivefury.rpf.utils import _build_rsc7, _resource_flags_from_size

    from gta_mod_manager.plugins.gta_v.rpf_archive import restore_stock_members

    stock = tmp_path / "stock" / "x64e.rpf"
    mods = tmp_path / "mods" / "x64e.rpf"
    stock.parent.mkdir()
    mods.parent.mkdir()

    # Stock-like resource: logical payload with explicit flags (not from_size defaults).
    logical = b"VANILLA_ADDER_YFT" + b"\x00" * 256
    sys_flags = _resource_flags_from_size(len(logical), 0) ^ 0x1111
    stock_blob = _build_rsc7(logical, version=0, sys_flags=sys_flags, gfx_flags=0)
    with RpfArchive.empty("x64e") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/vehicles.rpf")
        nested.add("adder.yft", stock_blob)
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(stock))

    mods.write_bytes(stock.read_bytes())
    replacement = tmp_path / "adder.yft"
    replacement.write_bytes(b"MODDED_ADDER_MESH" + b"\xff" * 64)
    import_members(
        mods,
        (
            ArchiveMemberImport(
                source_path=replacement,
                member_path="levels/gta5/vehicles.rpf/adder.yft",
            ),
        ),
    )

    result = restore_stock_members(
        mods, stock, ("levels/gta5/vehicles.rpf/adder.yft",)
    )
    assert result.restored == 1
    assert result.removed == 0
    assert result.changed == 1

    with RpfArchive.from_path(str(mods)) as loaded:
        nested = loaded.load_nested_archive(loaded.find_entry("levels/gta5/vehicles.rpf"))
        assert nested is not None
        entry = next(item for item in nested.iter_entries() if item.name == "adder.yft")
        assert nested.read_entry_bytes(entry) == logical
        assert isinstance(entry, RpfResourceFileEntry)
        assert entry.system_flags.value == sys_flags


def test_restore_deletes_when_mirrored_stock_lacks_member(tmp_path: Path) -> None:
    """Patchday cars in mods/x64e must uninstall via fallthrough delete."""
    from gta_mod_manager.plugins.gta_v.rpf_archive import restore_stock_members

    game = tmp_path / "game"
    stock = game / "x64e.rpf"
    mods = game / "mods" / "x64e.rpf"
    mods.parent.mkdir(parents=True)
    game.mkdir(exist_ok=True)

    # Stock x64e has adder only — not huntley (lives in DLC in real game).
    with RpfArchive.empty("x64e") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/vehicles.rpf")
        nested.add("adder.yft", b"VANILLA_ADDER")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(stock))

    mods.write_bytes(stock.read_bytes())
    huntley = tmp_path / "huntley.yft"
    huntley.write_bytes(b"MODDED_HUNTLEY")
    import_members(
        mods,
        (
            ArchiveMemberImport(
                source_path=huntley,
                member_path="levels/gta5/vehicles.rpf/huntley.yft",
            ),
        ),
    )

    result = restore_stock_members(
        mods,
        stock,
        ("levels/gta5/vehicles.rpf/huntley.yft",),
        game_root=game,
    )
    assert result.restored == 0
    assert result.removed == 1

    with RpfArchive.from_path(str(mods)) as loaded:
        nested = loaded.load_nested_archive(loaded.find_entry("levels/gta5/vehicles.rpf"))
        assert nested is not None
        names = {item.name for item in nested.iter_entries()}
        assert "huntley.yft" not in names
        assert "adder.yft" in names


def test_resolve_stock_members_finds_patchday_leaf(tmp_path: Path) -> None:
    from gta_mod_manager.plugins.gta_v.rpf_archive import resolve_stock_members

    game = tmp_path / "game"
    stock = game / "x64e.rpf"
    dlc = game / "update" / "x64" / "dlcpacks" / "patchday2ng" / "dlc.rpf"
    dlc.parent.mkdir(parents=True)
    game.mkdir(exist_ok=True)

    with RpfArchive.empty("x64e") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/vehicles.rpf")
        nested.add("adder.yft", b"VANILLA_ADDER")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(stock))

    with RpfArchive.empty("dlc") as outer:
        _entry, nested = outer.add_nested_archive("x64/levels/gta5/vehicles.rpf")
        nested.add("huntley.yft", b"VANILLA_HUNTLEY")
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(dlc))

    found = resolve_stock_members(
        stock,
        game,
        ("levels/gta5/vehicles.rpf/huntley.yft",),
    )
    assert "levels/gta5/vehicles.rpf/huntley.yft" in found
    source = found["levels/gta5/vehicles.rpf/huntley.yft"]
    assert source.archive_path == dlc
    assert source.nested_path == "x64/levels/gta5/vehicles.rpf"
    assert source.leaf == "huntley.yft"


def test_import_members_refuses_a_missing_archive(tmp_path: Path) -> None:
    source = tmp_path / "gauntlet.yft"
    source.write_bytes(b"data")
    with pytest.raises(InstallError):
        import_members(
            tmp_path / "missing.rpf",
            (
                ArchiveMemberImport(
                    source_path=source,
                    member_path="levels/gta5/vehicles.rpf/gauntlet.yft",
                ),
            ),
        )


def test_materialize_rebuilds_headerless_resource_bodies(tmp_path: Path) -> None:
    """Stock vehicles.rpf bodies lack RSC7 headers; materialize must wrap them."""
    from fivefury.rpf.entries import RpfResourceFileEntry
    from fivefury.rpf.utils import _build_rsc7, _is_rsc7, _resource_flags_from_size
    from fivefury.resource import parse_rsc7

    from gta_mod_manager.plugins.gta_v.rpf_archive import materialize_resources_for_write

    logical = b"x" * 4096
    sys_flags = _resource_flags_from_size(len(logical), 0)
    full = _build_rsc7(logical, version=0, sys_flags=sys_flags, gfx_flags=0)
    _header, payload = parse_rsc7(full)
    # Simulate a stock entry: compressed body only (no RSC7 magic).
    compressed_body = full[16:]
    assert not _is_rsc7(compressed_body)

    archive_path = tmp_path / "x64e.rpf"
    with RpfArchive.empty("x64e") as outer:
        _entry, nested = outer.add_nested_archive("levels/gta5/vehicles.rpf")
        nested.add("adder.yft", full)
        outer.encryption = OPEN_ENCRYPTION
        outer.save(str(archive_path))

    with RpfArchive.from_path(str(archive_path)) as loaded:
        nested = loaded.load_nested_archive(loaded.find_entry("levels/gta5/vehicles.rpf"))
        assert nested is not None
        target = next(
            item
            for item in nested.iter_entries()
            if isinstance(item, RpfResourceFileEntry) and item.name == "adder.yft"
        )
        # Force the headerless body into the entry the way stock archives behave.
        target._data = compressed_body
        rebuilt = materialize_resources_for_write(loaded)
        assert rebuilt >= 1
        assert _is_rsc7(bytes(target._data))
