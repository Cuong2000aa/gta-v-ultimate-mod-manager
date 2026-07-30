"""Tests for the filesystem helpers, especially the path-traversal guard."""

from __future__ import annotations

from pathlib import Path

import pytest

from gta_mod_manager.core.exceptions import SafetyViolationError
from gta_mod_manager.utils import fs


def test_safe_join_accepts_paths_inside_the_base(tmp_path: Path) -> None:
    joined = fs.safe_join(tmp_path, "mods/update/x64/dlcpacks/adder2/dlc.rpf")

    assert fs.is_relative_to(joined, tmp_path)


@pytest.mark.parametrize(
    "member",
    [
        "../escaped.dll",
        "mods/../../escaped.dll",
        "../../Windows/System32/evil.dll",
    ],
)
def test_safe_join_blocks_traversal(tmp_path: Path, member: str) -> None:
    with pytest.raises(SafetyViolationError):
        fs.safe_join(tmp_path, member)


def test_is_relative_to_ignores_case_on_windows(tmp_path: Path) -> None:
    child = tmp_path / "Mods" / "update"
    child.mkdir(parents=True)

    assert fs.is_relative_to(child, tmp_path)
    assert not fs.is_relative_to(tmp_path, child)


def test_iter_files_respects_the_depth_limit(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "b").mkdir()
    (tmp_path / "top.txt").write_text("x", encoding="utf-8")
    (tmp_path / "a" / "mid.txt").write_text("x", encoding="utf-8")
    (tmp_path / "a" / "b" / "deep.txt").write_text("x", encoding="utf-8")

    shallow = {item.name for item in fs.iter_files(tmp_path, max_depth=1)}
    everything = {item.name for item in fs.iter_files(tmp_path)}

    assert shallow == {"top.txt", "mid.txt"}
    assert everything == {"top.txt", "mid.txt", "deep.txt"}


def test_copy_file_creates_parents_and_can_refuse_overwriting(tmp_path: Path) -> None:
    source = tmp_path / "source.txt"
    source.write_text("payload", encoding="utf-8")
    destination = tmp_path / "nested" / "deeper" / "copy.txt"

    fs.copy_file(source, destination)
    assert destination.read_text(encoding="utf-8") == "payload"

    with pytest.raises(FileExistsError):
        fs.copy_file(source, destination, overwrite=False)


def test_delete_helpers_report_whether_anything_was_removed(tmp_path: Path) -> None:
    target = tmp_path / "file.txt"
    target.write_text("x", encoding="utf-8")
    tree = tmp_path / "tree" / "inner"
    tree.mkdir(parents=True)

    assert fs.delete_file(target)
    assert not fs.delete_file(target)
    assert fs.delete_tree(tmp_path / "tree")
    assert not fs.delete_tree(tmp_path / "tree")


def test_remove_empty_directories_stops_at_the_boundary(tmp_path: Path) -> None:
    deep = tmp_path / "keep" / "a" / "b" / "c"
    deep.mkdir(parents=True)

    removed = fs.remove_empty_directories(deep, stop_at=tmp_path / "keep")

    assert removed == 3
    assert (tmp_path / "keep").is_dir()


def test_unique_path_avoids_clobbering(tmp_path: Path) -> None:
    original = tmp_path / "mod.zip"
    original.write_bytes(b"x")

    assert fs.unique_path(original).name == "mod (2).zip"


def test_sanitise_name_strips_invalid_characters() -> None:
    assert fs.sanitise_name('bad:name?<>') == "bad_name___"
    assert fs.sanitise_name("   ") == "unnamed"


@pytest.mark.parametrize(
    ("size", "expected"),
    [(0, "0 B"), (512, "512 B"), (2048, "2.0 KB"), (5 * 1024 * 1024, "5.0 MB")],
)
def test_human_size_formats_binary_units(size: int, expected: str) -> None:
    assert fs.human_size(size) == expected
