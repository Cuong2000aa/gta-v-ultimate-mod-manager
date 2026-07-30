"""Tests for extraction, nested archives and inventory building."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from gta_mod_manager.core.app_paths import AppPaths
from gta_mod_manager.core.exceptions import SafetyViolationError, ScanError
from gta_mod_manager.scanner.package_scanner import PackageScanner, ScanOptions
from gta_mod_manager.scanner.workspace import TempWorkspace, purge_stale_workspaces


@pytest.fixture()
def workspace(app_paths: AppPaths):  # noqa: ANN201 - TempWorkspace
    """Yield a disposable extraction workspace."""
    with TempWorkspace(app_paths) as space:
        yield space


def test_a_loose_file_becomes_a_single_entry_inventory(
    tmp_path: Path, workspace: TempWorkspace
) -> None:
    loose = tmp_path / "ScriptHookV.dll"
    loose.write_bytes(b"MZ")

    inventory = PackageScanner().scan(loose, workspace.root)

    assert inventory.count == 1
    assert inventory.files[0].relative_path.name == "ScriptHookV.dll"


def test_a_zip_is_extracted_and_indexed(tmp_path: Path, workspace: TempWorkspace) -> None:
    archive = tmp_path / "mod.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("data/vehicles.meta", "<Root/>")
        bundle.writestr("dlc.rpf", b"payload")

    inventory = PackageScanner().scan(archive, workspace.root)

    names = {item.relative_path.as_posix() for item in inventory.files}
    assert names == {"data/vehicles.meta", "dlc.rpf"}
    assert inventory.total_size > 0


def test_a_single_wrapper_folder_is_flattened(
    tmp_path: Path, workspace: TempWorkspace
) -> None:
    archive = tmp_path / "wrapped.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("Cool Mod v1.2/scripts/Cool.dll", b"MZ")
        bundle.writestr("Cool Mod v1.2/readme.txt", "hello")

    inventory = PackageScanner().scan(archive, workspace.root)

    names = {item.relative_path.as_posix() for item in inventory.files}
    assert names == {"scripts/Cool.dll", "readme.txt"}


def test_nested_archives_are_expanded(tmp_path: Path, workspace: TempWorkspace) -> None:
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as bundle:
        bundle.writestr("inner.asi", b"MZ")

    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as bundle:
        bundle.writestr("payload/inner.zip", inner.read_bytes())
        bundle.writestr("payload/readme.txt", "read me")

    inventory = PackageScanner().scan(outer, workspace.root)

    names = {item.relative_path.name for item in inventory.files}
    assert "inner.asi" in names
    assert "inner.zip" not in names


def test_nesting_stops_at_the_configured_depth(
    tmp_path: Path, workspace: TempWorkspace
) -> None:
    inner = tmp_path / "inner.zip"
    with zipfile.ZipFile(inner, "w") as bundle:
        bundle.writestr("deep.asi", b"MZ")
    outer = tmp_path / "outer.zip"
    with zipfile.ZipFile(outer, "w") as bundle:
        bundle.writestr("inner.zip", inner.read_bytes())

    scanner = PackageScanner(options=ScanOptions(max_nested_depth=0))
    inventory = scanner.scan(outer, workspace.root)

    assert {item.relative_path.name for item in inventory.files} == {"inner.zip"}


def test_a_dropped_folder_is_copied_as_is(tmp_path: Path, workspace: TempWorkspace) -> None:
    source = tmp_path / "MyMod"
    (source / "scripts").mkdir(parents=True)
    (source / "scripts" / "Cool.dll").write_bytes(b"MZ")
    (source / "readme.txt").write_text("hello", encoding="utf-8")

    inventory = PackageScanner().scan(source, workspace.root)

    assert {item.relative_path.as_posix() for item in inventory.files} == {
        "scripts/Cool.dll",
        "readme.txt",
    }


def test_structural_folders_are_never_flattened_away(
    tmp_path: Path, workspace: TempWorkspace
) -> None:
    archive = tmp_path / "scripts-only.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("scripts/Cool.dll", b"MZ")

    inventory = PackageScanner().scan(archive, workspace.root)

    assert {item.relative_path.as_posix() for item in inventory.files} == {"scripts/Cool.dll"}


def test_a_dlc_pack_root_is_never_flattened_away(
    tmp_path: Path, workspace: TempWorkspace
) -> None:
    archive = tmp_path / "pack-only.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("adder2/setup2.xml", "<SSetupData/>")
        bundle.writestr("adder2/dlc.rpf", b"payload")

    inventory = PackageScanner().scan(archive, workspace.root)

    assert {item.relative_path.parts[0] for item in inventory.files} == {"adder2"}


def test_scanning_a_missing_source_raises(workspace: TempWorkspace) -> None:
    with pytest.raises(ScanError):
        PackageScanner().scan(Path("does-not-exist.zip"), workspace.root)


def test_a_zip_slip_entry_aborts_the_scan(tmp_path: Path, workspace: TempWorkspace) -> None:
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as bundle:
        bundle.writestr("../escaped.dll", b"MZ")
        bundle.writestr("safe.dll", b"MZ")

    with pytest.raises(SafetyViolationError):
        PackageScanner().scan(archive, workspace.root)

    assert not (tmp_path / "escaped.dll").exists()


def test_disposing_a_workspace_removes_it(app_paths: AppPaths) -> None:
    space = TempWorkspace(app_paths)
    root = space.root
    (root / "file.txt").write_text("x", encoding="utf-8")

    space.dispose()

    assert not root.exists()


def test_purging_stale_workspaces_clears_the_temp_folder(app_paths: AppPaths) -> None:
    leftover = app_paths.temp / "scan-leftover"
    (leftover / "inner").mkdir(parents=True)

    purge_stale_workspaces(app_paths)

    assert not leftover.exists()
    assert app_paths.temp.is_dir()
