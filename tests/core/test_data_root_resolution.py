from __future__ import annotations

from pathlib import Path

from gta_mod_manager.app import parse_arguments, resolve_paths
from gta_mod_manager.core import constants
from gta_mod_manager.core.data_root import write_data_root


def test_selected_data_root_is_used_by_default(
    tmp_path: Path, monkeypatch
) -> None:
    local = tmp_path / "local"
    selected = tmp_path / "selected"
    selected.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    write_data_root(selected)

    assert resolve_paths(parse_arguments([])).root == selected.resolve()


def test_explicit_data_dir_overrides_saved_selection(
    tmp_path: Path, monkeypatch
) -> None:
    local = tmp_path / "local"
    selected = tmp_path / "selected"
    explicit = tmp_path / "explicit"
    selected.mkdir()
    explicit.mkdir()
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    write_data_root(selected)

    resolved = resolve_paths(parse_arguments(["--data-dir", str(explicit)]))

    assert resolved.root == explicit
    assert (local / constants.DATA_ROOT_POINTER_FILE).is_file()
