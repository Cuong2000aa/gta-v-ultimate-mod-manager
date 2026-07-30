"""Unit tests for automatic dlclist.xml registration."""

from __future__ import annotations

from pathlib import Path

from fivefury import RpfArchive

from gta_mod_manager.plugins.gta_v.rpf_archive import (
    append_dlclist_entries,
    remove_dlclist_entries,
)
from tests.helpers.rpf_fixtures import write_minimal_update_rpf


def _read_dlclist(path: Path) -> str:
    with RpfArchive.from_path(str(path)) as archive:
        entry = archive.find_entry("common/data/dlclist.xml")
        assert entry is not None
        return archive.read_entry_bytes(entry).decode("utf-8", errors="replace")


def test_append_and_remove_dlclist_entries(tmp_path: Path) -> None:
    archive = write_minimal_update_rpf(tmp_path / "update.rpf")

    added = append_dlclist_entries(archive, ["adder2", "adder2", "lykan"])
    assert added == 2
    text = _read_dlclist(archive)
    assert "dlcpacks:/adder2/" in text
    assert "dlcpacks:/lykan/" in text
    assert "dlcpacks:/mpChristmas/" in text

    assert append_dlclist_entries(archive, ["adder2"]) == 0

    removed = remove_dlclist_entries(archive, ["adder2"])
    assert removed == 1
    text = _read_dlclist(archive)
    assert "dlcpacks:/adder2/" not in text
    assert "dlcpacks:/lykan/" in text
    assert "dlcpacks:/mpChristmas/" in text
